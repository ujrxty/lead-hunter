"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { aiApi } from "@/lib/api";
import type { EnrichedLead } from "@/lib/types";

export function LeadsSection() {
  const [statusFilter, setStatusFilter] = useState<string>("");

  const { data: leads, isLoading } = useQuery({
    queryKey: ["leads", statusFilter],
    queryFn: () => aiApi.getLeads(statusFilter || undefined),
    refetchInterval: 5000,
  });

  const counts = {
    all: leads?.length || 0,
    enriched: leads?.filter((l) => l.status === "enriched").length || 0,
    pending: leads?.filter((l) => l.status === "pending").length || 0,
    failed: leads?.filter((l) => l.status === "failed").length || 0,
  };

  return (
    <div className="space-y-8">
      <div className="flex items-end justify-between gap-4">
        <div>
          <span className="mono-label">Contacts</span>
          <h2 className="font-display text-3xl text-foreground mt-1 leading-none">Enriched Leads</h2>
          <p className="text-sm text-dim mt-2">Companies we&apos;ve traced to a website, inbox, and socials.</p>
        </div>
      </div>

      <div className="flex gap-1 p-1 rounded-lg bg-[var(--surface)] border border-border w-fit">
        <StatusTab label="All" count={counts.all} active={statusFilter === ""} onClick={() => setStatusFilter("")} />
        <StatusTab label="Enriched" count={counts.enriched} active={statusFilter === "enriched"} onClick={() => setStatusFilter("enriched")} />
        <StatusTab label="Pending" count={counts.pending} active={statusFilter === "pending"} onClick={() => setStatusFilter("pending")} />
        <StatusTab label="Failed" count={counts.failed} active={statusFilter === "failed"} onClick={() => setStatusFilter("failed")} />
      </div>

      {isLoading ? (
        <div className="grid gap-3 md:grid-cols-2">{[...Array(4)].map((_, i) => <LeadSkeleton key={i} />)}</div>
      ) : leads?.length === 0 ? (
        <EmptyState />
      ) : (
        <div className="grid gap-3 md:grid-cols-2">
          {leads?.map((lead, i) => <LeadCard key={lead.id} lead={lead} index={i} />)}
        </div>
      )}
    </div>
  );
}

function StatusTab({ label, count, active, onClick }: { label: string; count: number; active: boolean; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className={`flex items-center gap-2 px-3 py-1.5 rounded-md text-xs font-medium transition-all ${
        active ? "bg-[var(--surface-2)] text-foreground" : "text-faint hover:text-dim"
      }`}
    >
      {label}
      <span className={`font-mono text-[10px] px-1.5 py-0.5 rounded ${active ? "bg-signal text-[var(--signal-ink)]" : "bg-[var(--surface-2)] text-faint"}`}>
        {count}
      </span>
    </button>
  );
}

function LeadCard({ lead, index }: { lead: EnrichedLead; index: number }) {
  const hasContact = !!(lead.website || lead.emails?.length || lead.phones?.length || lead.linkedin || lead.twitter || lead.instagram || lead.facebook);
  const tone =
    lead.status === "enriched" ? { c: "var(--signal)", label: "Enriched" } :
    lead.status === "failed" ? { c: "var(--danger)", label: "Failed" } :
    { c: "var(--money)", label: "Pending" };

  return (
    <div
      className={`glass-card rounded-lg p-5 animate-slide-up ${lead.status === "enriched" && hasContact ? "signal-edge pl-6" : ""}`}
      style={{ animationDelay: `${index * 50}ms` }}
    >
      <div className="flex items-start justify-between gap-3 mb-4">
        <div className="min-w-0">
          <h3 className="text-[15px] font-semibold text-foreground truncate">{lead.company_name}</h3>
          {lead.description && <p className="text-xs text-dim mt-1 line-clamp-2">{lead.description}</p>}
        </div>
        <span
          className="flex items-center gap-1.5 px-2 py-1 rounded font-mono text-[10px] uppercase tracking-wider flex-shrink-0"
          style={{ color: tone.c, backgroundColor: `color-mix(in oklch, ${tone.c} 12%, transparent)`, border: `1px solid color-mix(in oklch, ${tone.c} 30%, transparent)` }}
        >
          {tone.label}
        </span>
      </div>

      {lead.status === "enriched" && (hasContact ? (
        <>
          <div className="space-y-2 mb-3">
            {lead.website && <ContactRow icon={<GlobeIcon />} value={lead.website} isLink />}
            {lead.emails?.length > 0 && <ContactRow icon={<MailIcon />} value={lead.emails.join(", ")} />}
            {lead.phones?.length > 0 && <ContactRow icon={<PhoneIcon />} value={lead.phones.join(", ")} />}
          </div>
          {(lead.linkedin || lead.twitter || lead.instagram || lead.facebook) && (
            <div className="flex flex-wrap gap-1.5 pt-3 border-t border-border">
              {lead.linkedin && <SocialLink href={lead.linkedin} label="LinkedIn" />}
              {lead.twitter && <SocialLink href={lead.twitter} label="Twitter" />}
              {lead.instagram && <SocialLink href={lead.instagram} label="Instagram" />}
              {lead.facebook && <SocialLink href={lead.facebook} label="Facebook" />}
            </div>
          )}
        </>
      ) : (
        <p className="text-xs text-faint">No public contact info found — likely a product name, not a real company.</p>
      ))}

      {lead.status === "pending" && (
        <div className="flex items-center gap-2 text-xs text-money font-mono">
          <Spinner /> tracing contact data…
        </div>
      )}
      {lead.status === "failed" && (
        <p className="text-xs text-[var(--danger)]">Enrichment failed — no public contact info located.</p>
      )}
    </div>
  );
}

function ContactRow({ icon, value, isLink = false }: { icon: React.ReactNode; value: string; isLink?: boolean }) {
  return (
    <div className="flex items-center gap-2.5 text-sm font-mono">
      <span className="text-faint flex-shrink-0">{icon}</span>
      {isLink ? (
        <a href={value.startsWith("http") ? value : `https://${value}`} target="_blank" rel="noopener noreferrer"
           className="text-signal hover:underline truncate">{value.replace(/^https?:\/\//, "")}</a>
      ) : (
        <span className="text-foreground truncate">{value}</span>
      )}
    </div>
  );
}

function SocialLink({ href, label }: { href: string; label: string }) {
  return (
    <a href={href} target="_blank" rel="noopener noreferrer"
       className="px-2.5 py-1 text-xs font-mono rounded border border-border text-dim hover:text-signal hover:border-[var(--signal)] transition-colors">
      {label}
    </a>
  );
}

function LeadSkeleton() {
  return (
    <div className="glass-card rounded-lg p-5">
      <div className="flex items-start justify-between mb-4">
        <div>
          <div className="h-5 w-32 rounded skeleton-shimmer" />
          <div className="h-3 w-48 rounded skeleton-shimmer mt-2" />
        </div>
        <div className="h-5 w-16 rounded skeleton-shimmer" />
      </div>
      <div className="space-y-2">
        <div className="h-3 w-40 rounded skeleton-shimmer" />
        <div className="h-3 w-36 rounded skeleton-shimmer" />
      </div>
    </div>
  );
}

function EmptyState() {
  return (
    <div className="text-center py-16 glass-card rounded-xl">
      <div className="w-14 h-14 mx-auto mb-4 rounded-lg bg-[var(--surface-2)] border border-border flex items-center justify-center">
        <MailIcon className="w-6 h-6 text-faint" />
      </div>
      <h3 className="font-display text-xl text-foreground mb-1">No leads yet</h3>
      <p className="text-sm text-dim max-w-sm mx-auto">
        On the Signal tab, hit the enrich button on any job with a company signal to pull its contact info.
      </p>
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
const GlobeIcon = () => (<svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9a9 9 0 01-9-9m9 9c1.657 0 3-4.03 3-9s-1.343-9-3-9m0 18c-1.657 0-3-4.03-3-9s1.343-9 3-9m-9 9a9 9 0 019-9" /></svg>);
const MailIcon = ({ className = "w-4 h-4" }: { className?: string }) => (<svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" /></svg>);
const PhoneIcon = () => (<svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z" /></svg>);
