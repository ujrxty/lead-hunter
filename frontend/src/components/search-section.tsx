"use client";

import { useState, useEffect } from "react";
import { createPortal } from "react-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { jobsApi, aiApi } from "@/lib/api";
import type { Job } from "@/lib/types";

export function SearchSection() {
  const [keywords, setKeywords] = useState<string[]>([]);
  const [inputValue, setInputValue] = useState("");
  const [expandedJob, setExpandedJob] = useState<number | null>(null);
  const [showCompanyOnly, setShowCompanyOnly] = useState(false);
  const [proposalJob, setProposalJob] = useState<Job | null>(null);
  const [page, setPage] = useState(1);
  const perPage = 20;
  const queryClient = useQueryClient();

  const { data: stats } = useQuery({ queryKey: ["stats"], queryFn: jobsApi.getStats });

  const { data: recommendations } = useQuery({
    queryKey: ["recommendations"],
    queryFn: aiApi.getRecommendations,
    refetchInterval: 60000,
  });

  const { data: profile } = useQuery({ queryKey: ["profile"], queryFn: aiApi.getProfile });

  const { data: jobsData, isLoading: loadingJobs } = useQuery({
    queryKey: ["jobs", showCompanyOnly, page],
    queryFn: () => jobsApi.getJobs({ only_company_mentions: showCompanyOnly, page, per_page: perPage }),
  });

  // Depth = number of Upwork result pages to walk (each ~10 jobs).
  // 0 = "everything Upwork will give us" (hard-capped at 100 pages in the scraper).
  const [depth, setDepth] = useState<number>(10);

  const searchMutation = useMutation({
    mutationFn: (kw: string[]) => jobsApi.searchJobs({ keywords: kw, search_type: "OR", max_pages: depth }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
      queryClient.invalidateQueries({ queryKey: ["stats"] });
    },
  });

  const enrichMutation = useMutation({
    mutationFn: aiApi.enrichLead,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["leads"] }),
  });

  const addKeyword = () => {
    const v = inputValue.trim();
    if (v && !keywords.includes(v)) {
      setKeywords([...keywords, v]);
      setInputValue("");
    }
  };
  const removeKeyword = (kw: string) => setKeywords(keywords.filter((k) => k !== kw));
  const useAIKeywords = () => {
    if (profile?.generated_keywords) setKeywords(profile.generated_keywords.slice(0, 6));
  };
  const handleSearch = () => keywords.length > 0 && searchMutation.mutate(keywords);

  const totalPages = jobsData ? Math.ceil(jobsData.total / perPage) : 1;

  return (
    <div className="space-y-10">
      {/* ===== Metrics ===== */}
      <section>
        <div className="flex items-center gap-3 mb-4">
          <span className="mono-label">Overview</span>
          <span className="flex-1 divider-gradient" />
        </div>
        <div className="grid grid-cols-3 gap-px rounded-lg overflow-hidden border border-border bg-[var(--line)]">
          <StatCell value={stats?.total_jobs ?? 0} label="Jobs Tracked" accent="text" index={0} />
          <StatCell value={stats?.jobs_with_company ?? 0} label="Company Signals" accent="signal" index={1} />
          <StatCell value={stats?.bookmarked_jobs ?? 0} label="Bookmarked" accent="money" index={2} />
        </div>
      </section>

      {/* ===== Hot signals ===== */}
      {recommendations?.hot_leads && recommendations.hot_leads.length > 0 && (
        <section>
          <div className="flex items-center gap-3 mb-4">
            <span className="mono-label text-signal">Hot Signals</span>
            <span className="text-faint font-mono text-[11px]">
              {recommendations.hot_leads.length} high-score {recommendations.hot_leads.length === 1 ? "match" : "matches"}
            </span>
            <span className="flex-1 divider-gradient" />
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {recommendations.hot_leads.slice(0, 4).map((lead, i) => (
              <a
                key={lead.id}
                href={lead.url}
                target="_blank"
                rel="noopener noreferrer"
                className="group glass-card signal-edge rounded-lg p-4 pl-5 hover-lift animate-slide-up"
                style={{ animationDelay: `${i * 60}ms` }}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2 mb-2">
                      <ScorePill score={lead.score} />
                      {lead.detected_company_name && (
                        <span className="font-mono text-[11px] text-dim truncate">{lead.detected_company_name}</span>
                      )}
                    </div>
                    <h3 className="text-sm font-medium leading-snug text-foreground line-clamp-2 group-hover:text-signal transition-colors">
                      {lead.title}
                    </h3>
                    <div className="flex items-center gap-3 mt-2.5 font-mono text-[11px]">
                      {lead.client_rating != null && <Rating value={lead.client_rating} />}
                      {lead.budget_min != null && (
                        <span className="text-money">${lead.budget_min}{lead.budget_type === "hourly" ? "/hr" : ""}</span>
                      )}
                    </div>
                  </div>
                  <ArrowIcon className="w-4 h-4 text-faint group-hover:text-signal transition-colors flex-shrink-0" />
                </div>
              </a>
            ))}
          </div>
        </section>
      )}

      {/* ===== Search console ===== */}
      <section className="glass-card rounded-xl p-6">
        <div className="flex items-start justify-between gap-4 mb-5">
          <div>
            <span className="mono-label">Query</span>
            <h2 className="font-display text-2xl text-foreground mt-1 leading-none">Hunt the board</h2>
            <p className="text-sm text-dim mt-2">Scrape Upwork by keyword — we flag the ones naming a real company.</p>
          </div>
          {profile?.generated_keywords && (
            <button
              onClick={useAIKeywords}
              className="btn-ghost inline-flex items-center gap-2 px-3.5 py-2 rounded-md text-xs font-medium whitespace-nowrap"
            >
              <SparkIcon className="w-3.5 h-3.5 text-signal" />
              AI keywords
            </button>
          )}
        </div>

        <div className="flex gap-2">
          <div className="flex-1 relative">
            <span className="absolute left-3.5 top-1/2 -translate-y-1/2 font-mono text-signal text-sm select-none">&gt;</span>
            <input
              type="text"
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && addKeyword()}
              placeholder="type a keyword, hit enter…"
              className="w-full h-12 pl-9 pr-4 rounded-md floating-input font-mono text-sm text-foreground focus-ring"
            />
          </div>
          <button
            onClick={handleSearch}
            disabled={keywords.length === 0 || searchMutation.isPending}
            className="h-12 px-6 rounded-md btn-primary disabled:opacity-40 disabled:cursor-not-allowed disabled:transform-none flex items-center gap-2 text-sm"
          >
            {searchMutation.isPending ? <Spinner /> : <SearchIcon className="w-4 h-4" />}
            {searchMutation.isPending ? "Scraping…" : "Run"}
          </button>
        </div>

        {/* Depth selector — how deep to scrape */}
        <div className="flex flex-wrap items-center gap-2 mt-4">
          <span className="mono-label mr-1">Depth</span>
          {[
            { v: 5, label: "5 pages", jobs: "~50" },
            { v: 10, label: "10 pages", jobs: "~100" },
            { v: 25, label: "25 pages", jobs: "~250" },
            { v: 50, label: "50 pages", jobs: "~500" },
            { v: 0, label: "All", jobs: "unlimited" },
          ].map((opt) => (
            <button
              key={opt.v}
              onClick={() => setDepth(opt.v)}
              className={`px-2.5 py-1 rounded-md font-mono text-[11px] transition-all ${
                depth === opt.v
                  ? "bg-signal text-[var(--signal-ink)] font-semibold"
                  : "border border-border text-dim hover:text-foreground hover:border-[var(--line-strong)]"
              }`}
              title={`${opt.jobs} jobs`}
            >
              {opt.label}
            </button>
          ))}
          <span className="font-mono text-[11px] text-faint ml-auto">
            {depth === 0 ? "unlimited (may take several minutes)" : `~${depth * 10} jobs, ~${Math.ceil(depth * 8 / 60)}m`}
          </span>
        </div>

        {keywords.length > 0 && (
          <div className="flex flex-wrap gap-2 mt-4">
            {keywords.map((kw) => (
              <span key={kw} className="chip animate-scale-in !text-foreground !border-[var(--signal)]/40">
                {kw}
                <button onClick={() => removeKeyword(kw)} className="text-faint hover:text-signal transition-colors">
                  <XIcon className="w-3 h-3" />
                </button>
              </span>
            ))}
          </div>
        )}

        {searchMutation.isSuccess && (
          <div className="mt-4 px-4 py-3 rounded-md badge-success flex items-center gap-2 text-sm animate-fade-in">
            <CheckIcon className="w-4 h-4" />
            <span className="font-mono text-xs">
              {searchMutation.data.total_found} jobs · {searchMutation.data.with_company_mention} with a company signal
            </span>
          </div>
        )}
        {searchMutation.isError && (
          <div className="mt-4 px-4 py-3 rounded-md text-sm text-[var(--danger)] border border-[var(--danger)]/30 bg-[var(--danger)]/10 font-mono text-xs">
            Scrape failed — is the backend running and Chrome installed?
          </div>
        )}
      </section>

      {/* ===== Board ===== */}
      <section>
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <span className="mono-label">The Board</span>
            <span className="text-faint font-mono text-[11px]">{jobsData?.total ?? 0} results</span>
          </div>
          <Toggle
            checked={showCompanyOnly}
            onChange={(v) => { setShowCompanyOnly(v); setPage(1); }}
            label="Company signals only"
          />
        </div>

        <div className="space-y-3">
          {loadingJobs ? (
            [...Array(5)].map((_, i) => <JobSkeleton key={i} />)
          ) : jobsData?.jobs.length === 0 ? (
            <EmptyState />
          ) : (
            jobsData?.jobs.map((job, i) => (
              <JobCard
                key={job.id}
                job={job}
                expanded={expandedJob === job.id}
                onToggle={() => setExpandedJob(expandedJob === job.id ? null : job.id)}
                onEnrich={() => enrichMutation.mutate(job.id)}
                onGenerateProposal={() => setProposalJob(job)}
                isEnriching={enrichMutation.isPending}
                index={i}
              />
            ))
          )}
        </div>

        {jobsData && jobsData.total > perPage && (
          <div className="flex items-center justify-center gap-1.5 pt-6">
            <PageBtn onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page === 1}>Prev</PageBtn>
            {Array.from({ length: totalPages }, (_, i) => i + 1)
              .filter((p) => p === 1 || p === totalPages || Math.abs(p - page) <= 1)
              .map((p, i, arr) => (
                <span key={p} className="flex items-center">
                  {i > 0 && arr[i - 1] !== p - 1 && <span className="px-1.5 text-faint font-mono text-xs">…</span>}
                  <button
                    onClick={() => setPage(p)}
                    className={`w-9 h-9 rounded-md font-mono text-xs transition-colors ${
                      page === p ? "bg-signal text-[var(--signal-ink)] font-semibold" : "text-dim hover:text-foreground hover:bg-[var(--surface-2)]"
                    }`}
                  >
                    {p}
                  </button>
                </span>
              ))}
            <PageBtn onClick={() => setPage((p) => Math.min(totalPages, p + 1))} disabled={page >= totalPages}>Next</PageBtn>
          </div>
        )}
      </section>

      {proposalJob && <ProposalModal job={proposalJob} onClose={() => setProposalJob(null)} />}
    </div>
  );
}

/* ---------- Metrics ---------- */
function StatCell({ value, label, accent, index }: { value: number; label: string; accent: "text" | "signal" | "money"; index: number }) {
  const color = accent === "signal" ? "var(--signal)" : accent === "money" ? "var(--money)" : "var(--text)";
  return (
    <div className="relative bg-[var(--surface)] p-5 animate-slide-up" style={{ animationDelay: `${index * 70}ms` }}>
      <div className="display-num text-5xl" style={{ color }}>{value.toLocaleString()}</div>
      <div className="mono-label mt-3">{label}</div>
      <span className="absolute bottom-0 left-5 h-[2px] w-8 rounded-full" style={{ background: color, opacity: 0.6 }} />
    </div>
  );
}

/* ---------- Job card ---------- */
function JobCard({
  job, expanded, onToggle, onEnrich, onGenerateProposal, isEnriching, index,
}: {
  job: Job; expanded: boolean; onToggle: () => void; onEnrich: () => void;
  onGenerateProposal: () => void; isEnriching: boolean; index: number;
}) {
  const calculateScore = () => {
    let score = 50;
    if (job.company_confidence > 0.9) score += 15;
    else if (job.company_confidence > 0.8) score += 10;
    if (job.client_rating) {
      if (job.client_rating >= 4.8) score += 15;
      else if (job.client_rating >= 4.5) score += 10;
      else if (job.client_rating >= 4.0) score += 5;
    }
    if (job.client_total_spent) {
      const s = job.client_total_spent.toLowerCase();
      if (s.includes("k") || s.includes("000")) score += 10;
      if (s.includes("m")) score += 20;
    }
    if (job.budget_min && job.budget_min > 50) score += 10;
    return Math.min(score, 100);
  };
  const score = job.has_company_mention ? calculateScore() : 0;

  return (
    <div
      className={`glass-card rounded-lg hover-lift animate-slide-up ${job.has_company_mention ? "signal-edge" : ""}`}
      style={{ animationDelay: `${index * 25}ms` }}
    >
      <div className="p-5 pl-6">
        <div className="flex items-start justify-between gap-4 mb-3">
          <div className="flex flex-wrap items-center gap-2">
            {job.has_company_mention && score > 0 && <ScorePill score={score} />}
            {job.posted_at && (
              <span className="chip !border-transparent !text-faint !px-0 gap-1.5">
                <ClockIcon className="w-3 h-3" /> {formatTimeAgo(job.posted_at)}
              </span>
            )}
            {job.has_company_mention && job.detected_company_name && (
              <span className="badge-primary px-2 py-0.5 rounded text-[11px] font-mono">{job.detected_company_name}</span>
            )}
            {job.experience_level && <span className="chip">{job.experience_level}</span>}
          </div>

          <div className="flex items-center gap-0.5 flex-shrink-0">
            {job.has_company_mention && (
              <>
                <IconBtn onClick={(e) => { e.stopPropagation(); onEnrich(); }} disabled={isEnriching} title="Enrich contact info" tone="signal">
                  {isEnriching ? <Spinner size="sm" /> : <EnrichIcon className="w-4 h-4" />}
                </IconBtn>
                <IconBtn onClick={(e) => { e.stopPropagation(); onGenerateProposal(); }} title="Generate proposal" tone="money">
                  <SparkIcon className="w-4 h-4" />
                </IconBtn>
              </>
            )}
            <a href={job.url} target="_blank" rel="noopener noreferrer" title="Open on Upwork"
               className="p-2 rounded-md text-faint hover:text-foreground hover:bg-[var(--surface-2)] transition-all">
              <ArrowIcon className="w-4 h-4" />
            </a>
            <button onClick={onToggle} className="p-2 rounded-md text-faint hover:text-foreground hover:bg-[var(--surface-2)] transition-all">
              <ChevronIcon className={`w-4 h-4 transition-transform duration-200 ${expanded ? "rotate-180" : ""}`} />
            </button>
          </div>
        </div>

        <h3 className="text-[15px] font-semibold text-foreground leading-snug mb-3">{job.title}</h3>

        <div className="flex flex-wrap items-center gap-x-4 gap-y-2 font-mono text-[12px] mb-3">
          {job.client_rating != null && <Rating value={job.client_rating} />}
          {job.client_total_spent && <span className="text-money">{job.client_total_spent}</span>}
          {job.client_country && <span className="text-dim inline-flex items-center gap-1"><PinIcon className="w-3.5 h-3.5" />{job.client_country}</span>}
          {job.budget_type && (
            <span className="text-signal">
              {job.budget_type === "hourly" ? `$${job.budget_min}–$${job.budget_max}/hr` : `$${job.budget_min} fixed`}
            </span>
          )}
          {job.duration && <span className="text-faint">{cleanDuration(job.duration)}</span>}
        </div>

        <p className={`text-sm text-dim leading-relaxed ${expanded ? "" : "line-clamp-2"}`}>{job.description}</p>

        {job.search_keywords && job.search_keywords.length > 0 && (
          <div className="flex flex-wrap gap-1.5 mt-4">
            {job.search_keywords.slice(0, expanded ? undefined : 5).map((s) => <span key={s} className="chip">{s}</span>)}
            {!expanded && job.search_keywords.length > 5 && <span className="chip">+{job.search_keywords.length - 5}</span>}
          </div>
        )}
      </div>

      {expanded && job.company_context && (
        <div className="px-6 pb-5 pt-4 border-t border-border animate-fade-in">
          <div className="mono-label mb-2 text-signal">Signal Context</div>
          <p className="text-sm text-foreground leading-relaxed border-l-2 border-[var(--signal)]/40 pl-3">
            &ldquo;{job.company_context}&rdquo;
          </p>
        </div>
      )}
    </div>
  );
}

/* ---------- Proposal modal ---------- */
function ProposalModal({ job, onClose }: { job: Job; onClose: () => void }) {
  const [tone, setTone] = useState<"professional" | "friendly" | "enthusiastic">("professional");
  const [copied, setCopied] = useState(false);
  const [mounted, setMounted] = useState(false);
  const proposalMutation = useMutation({ mutationFn: () => aiApi.generateProposal(job.id, tone) });

  useEffect(() => {
    setMounted(true);
    // Lock body scroll while modal is open
    const original = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => { document.body.style.overflow = original; };
  }, []);

  const handleCopy = async () => {
    if (proposalMutation.data?.full_proposal) {
      await navigator.clipboard.writeText(proposalMutation.data.full_proposal);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  if (!mounted) return null;

  return createPortal(
    <div className="fixed inset-0 z-[200] flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/80 backdrop-blur-sm animate-fade-in" onClick={onClose} />
      <div
        className="relative w-full max-w-3xl max-h-[86vh] overflow-hidden rounded-xl animate-scale-in"
        style={{ background: "var(--surface)", border: "1px solid var(--line)" }}
      >
        <div className="flex items-center justify-between p-5 border-b border-border">
          <div className="min-w-0">
            <span className="mono-label text-money">Proposal Draft</span>
            <h2 className="font-display text-xl text-foreground mt-1 line-clamp-1">{job.title}</h2>
          </div>
          <button onClick={onClose} className="p-2 rounded-md hover:bg-[var(--surface-2)] text-faint hover:text-foreground transition-colors">
            <XIcon className="w-5 h-5" />
          </button>
        </div>

        <div className="flex flex-wrap items-center gap-3 p-5 border-b border-border">
          <span className="mono-label">Tone</span>
          <div className="flex gap-1.5">
            {(["professional", "friendly", "enthusiastic"] as const).map((t) => (
              <button
                key={t}
                onClick={() => setTone(t)}
                className={`px-3 py-1.5 rounded-md text-xs font-medium transition-all ${
                  tone === t ? "bg-signal text-[var(--signal-ink)]" : "btn-ghost"
                }`}
              >
                {t.charAt(0).toUpperCase() + t.slice(1)}
              </button>
            ))}
          </div>
          <button onClick={() => proposalMutation.mutate()} disabled={proposalMutation.isPending}
                  className="ml-auto px-4 py-2 rounded-md btn-primary text-xs flex items-center gap-2">
            {proposalMutation.isPending ? <><Spinner size="sm" /> Generating…</> : <><SparkIcon className="w-3.5 h-3.5" /> Generate</>}
          </button>
        </div>

        <div className="p-5 overflow-y-auto max-h-[calc(86vh-190px)]">
          {!proposalMutation.data && !proposalMutation.isPending && (
            <div className="text-center py-14 text-faint">
              <SparkIcon className="w-10 h-10 mx-auto mb-3 opacity-40" />
              <p className="text-sm">Pick a tone and hit generate. Needs a saved profile + Groq key.</p>
            </div>
          )}
          {proposalMutation.isError && (
            <p className="text-center py-14 text-sm text-[var(--danger)]">Couldn&apos;t generate — create a profile in the Profile tab first.</p>
          )}
          {proposalMutation.isPending && (
            <div className="space-y-4">
              {[...Array(4)].map((_, i) => (
                <div key={i} className="space-y-2">
                  <div className="h-3 w-24 skeleton-shimmer rounded" />
                  <div className="h-20 skeleton-shimmer rounded-md" />
                </div>
              ))}
            </div>
          )}
          {proposalMutation.data && (
            <div className="space-y-6 animate-fade-in">
              <ProposalSection title="Cover Letter" content={proposalMutation.data.cover_letter} />
              <ProposalSection title="Why I'm the Right Fit" content={proposalMutation.data.why_fit} />
              <ProposalSection title="My Approach" content={proposalMutation.data.approach} />
              <ProposalSection title="Timeline" content={proposalMutation.data.timeline} />
              {proposalMutation.data.questions.length > 0 && (
                <ProposalSection title="Questions for Client" content={proposalMutation.data.questions.map((q) => `• ${q}`).join("\n")} />
              )}
              <div className="pt-5 border-t border-border">
                <div className="flex items-center justify-between mb-3">
                  <span className="mono-label">Full Proposal</span>
                  <button onClick={handleCopy} className="btn-ghost flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs">
                    {copied ? <><CheckIcon className="w-3.5 h-3.5 text-signal" /> Copied</> : <><CopyIcon className="w-3.5 h-3.5" /> Copy</>}
                  </button>
                </div>
                <div className="p-4 rounded-md bg-[var(--bg-2)] border border-border">
                  <pre className="text-sm text-foreground whitespace-pre-wrap font-sans leading-relaxed">{proposalMutation.data.full_proposal}</pre>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>,
    document.body
  );
}

function ProposalSection({ title, content }: { title: string; content: string }) {
  return (
    <div>
      <div className="mono-label mb-2">{title}</div>
      <div className="p-4 rounded-md bg-[var(--surface-2)]/40 border border-border">
        <p className="text-sm text-dim leading-relaxed whitespace-pre-wrap">{content}</p>
      </div>
    </div>
  );
}

/* ---------- Small pieces ---------- */
function ScorePill({ score }: { score: number }) {
  const color = score >= 70 ? "var(--signal)" : score >= 55 ? "var(--money)" : "var(--text-faint)";
  return (
    <span
      className="inline-flex items-center gap-1 px-2 py-0.5 rounded font-mono text-[11px] font-semibold"
      style={{ color, backgroundColor: `color-mix(in oklch, ${color} 14%, transparent)`, border: `1px solid color-mix(in oklch, ${color} 32%, transparent)` }}
    >
      {score}<span className="opacity-60">%</span>
    </span>
  );
}

function Rating({ value }: { value: number }) {
  return (
    <span className="inline-flex items-center gap-1 text-money">
      <svg className="w-3.5 h-3.5 fill-current" viewBox="0 0 20 20"><path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" /></svg>
      {value.toFixed(2)}
    </span>
  );
}

function Toggle({ checked, onChange, label }: { checked: boolean; onChange: (v: boolean) => void; label: string }) {
  return (
    <label className="flex items-center gap-2.5 cursor-pointer group select-none">
      <span className="font-mono text-[11px] text-dim group-hover:text-foreground transition-colors">{label}</span>
      <button
        type="button"
        onClick={() => onChange(!checked)}
        className={`relative w-9 h-5 rounded-full transition-colors ${checked ? "bg-signal" : "bg-[var(--surface-3)]"}`}
      >
        <span className={`absolute top-0.5 left-0.5 w-4 h-4 rounded-full bg-[var(--bg)] transition-transform ${checked ? "translate-x-4" : ""}`} />
      </button>
    </label>
  );
}

function IconBtn({ children, onClick, disabled, title, tone }: {
  children: React.ReactNode; onClick: (e: React.MouseEvent) => void; disabled?: boolean; title: string; tone: "signal" | "money";
}) {
  const c = tone === "signal" ? "var(--signal)" : "var(--money)";
  return (
    <button onClick={onClick} disabled={disabled} title={title}
      className="p-2 rounded-md hover:bg-[var(--surface-2)] disabled:opacity-40 transition-all"
      style={{ color: c }}>
      {children}
    </button>
  );
}

function PageBtn({ children, onClick, disabled }: { children: React.ReactNode; onClick: () => void; disabled?: boolean }) {
  return (
    <button onClick={onClick} disabled={disabled}
      className="px-3.5 h-9 rounded-md font-mono text-xs text-dim hover:text-foreground hover:bg-[var(--surface-2)] disabled:opacity-30 disabled:cursor-not-allowed transition-colors">
      {children}
    </button>
  );
}

function JobSkeleton() {
  return (
    <div className="glass-card rounded-lg p-5 pl-6">
      <div className="flex items-center gap-2 mb-4">
        <div className="h-5 w-14 rounded skeleton-shimmer" />
        <div className="h-5 w-24 rounded skeleton-shimmer" />
      </div>
      <div className="h-5 w-3/4 rounded skeleton-shimmer mb-3" />
      <div className="flex gap-3 mb-3">
        <div className="h-3 w-16 rounded skeleton-shimmer" />
        <div className="h-3 w-20 rounded skeleton-shimmer" />
      </div>
      <div className="h-3 w-full rounded skeleton-shimmer mb-2" />
      <div className="h-3 w-2/3 rounded skeleton-shimmer" />
    </div>
  );
}

function EmptyState() {
  return (
    <div className="text-center py-20 glass-card rounded-xl">
      <div className="w-14 h-14 mx-auto mb-4 rounded-lg bg-[var(--surface-2)] border border-border flex items-center justify-center">
        <SearchIcon className="w-6 h-6 text-faint" />
      </div>
      <h3 className="font-display text-xl text-foreground mb-2">Nothing on the board</h3>
      <p className="text-sm text-dim max-w-sm mx-auto">Run a search above, or switch off the company filter to see everything.</p>
    </div>
  );
}

/* ---------- Icons & utils ---------- */
function Spinner({ size = "md" }: { size?: "sm" | "md" }) {
  const s = size === "sm" ? "w-4 h-4" : "w-5 h-5";
  return (
    <svg className={`${s} animate-spin`} fill="none" viewBox="0 0 24 24">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
    </svg>
  );
}
const SearchIcon = (p: { className?: string }) => (<svg className={p.className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" /></svg>);
const SparkIcon = (p: { className?: string }) => (<svg className={p.className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" /></svg>);
const EnrichIcon = (p: { className?: string }) => (<svg className={p.className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" /></svg>);
const ArrowIcon = (p: { className?: string }) => (<svg className={p.className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" /></svg>);
const ChevronIcon = (p: { className?: string }) => (<svg className={p.className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" /></svg>);
const XIcon = (p: { className?: string }) => (<svg className={p.className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" /></svg>);
const CheckIcon = (p: { className?: string }) => (<svg className={p.className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" /></svg>);
const CopyIcon = (p: { className?: string }) => (<svg className={p.className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" /></svg>);
const ClockIcon = (p: { className?: string }) => (<svg className={p.className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>);
const PinIcon = (p: { className?: string }) => (<svg className={p.className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" /><path strokeLinecap="round" strokeLinejoin="round" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" /></svg>);

function cleanDuration(d: string): string {
  return d.replace(/^Est\.?\s*(time)?[:\s]*/i, "").trim();
}
function formatTimeAgo(dateString: string): string {
  const date = new Date(dateString);
  const diffMs = Date.now() - date.getTime();
  const m = Math.floor(diffMs / 60000), h = Math.floor(m / 60), d = Math.floor(h / 24);
  if (m < 1) return "just now";
  if (m < 60) return `${m}m ago`;
  if (h < 24) return `${h}h ago`;
  if (d < 7) return `${d}d ago`;
  return date.toLocaleDateString();
}
