import axios from "axios";
import type {
  Job,
  JobListResponse,
  SearchRequest,
  SearchResponse,
  SearchQuery,
  Stats,
  UserProfile,
  EnrichedLead,
  LeadAnalysis,
} from "./types";

/**
 * API base URL resolution priority:
 *   1. localStorage "apiBaseUrl"  (user override from Settings UI)
 *   2. NEXT_PUBLIC_API_URL         (build-time env)
 *   3. http://localhost:8500/api   (default for local dev)
 */
const DEFAULT_API_URL = "http://localhost:8500/api";
export const API_URL_KEY = "apiBaseUrl";

export function getApiBaseUrl(): string {
  if (typeof window !== "undefined") {
    const stored = window.localStorage.getItem(API_URL_KEY);
    if (stored && stored.trim()) return stored.trim();
  }
  return process.env.NEXT_PUBLIC_API_URL || DEFAULT_API_URL;
}

const api = axios.create({
  baseURL: getApiBaseUrl(),
  headers: {
    "Content-Type": "application/json",
  },
});

export function setApiBaseUrl(url: string) {
  if (typeof window === "undefined") return;
  const trimmed = url.trim().replace(/\/+$/, "");
  if (trimmed) {
    window.localStorage.setItem(API_URL_KEY, trimmed);
  } else {
    window.localStorage.removeItem(API_URL_KEY);
  }
  // Rebuild the axios instance so subsequent calls hit the new URL
  api.defaults.baseURL = getApiBaseUrl();
}

export const jobsApi = {
  getJobs: async (params: {
    page?: number;
    per_page?: number;
    only_company_mentions?: boolean;
    search?: string;
    bookmarked?: boolean;
    min_confidence?: number;
  }): Promise<JobListResponse> => {
    const { data } = await api.get("/jobs", { params });
    return data;
  },

  getJob: async (id: number): Promise<Job> => {
    const { data } = await api.get(`/jobs/${id}`);
    return data;
  },

  updateJob: async (
    id: number,
    update: Partial<{
      is_bookmarked: boolean;
      is_hidden: boolean;
      notes: string;
    }>
  ): Promise<Job> => {
    const { data } = await api.patch(`/jobs/${id}`, update);
    return data;
  },

  searchJobs: async (request: SearchRequest): Promise<SearchResponse> => {
    const { data } = await api.post("/jobs/search", request, { timeout: 120000 });
    return data;
  },

  getSearchHistory: async (): Promise<SearchQuery[]> => {
    const { data } = await api.get("/jobs/queries/history");
    return data;
  },

  getStats: async (): Promise<Stats> => {
    const { data } = await api.get("/jobs/stats/overview");
    return data;
  },
};

export const aiApi = {
  getProfile: async (): Promise<UserProfile | null> => {
    const { data } = await api.get("/ai/profile");
    return data;
  },

  saveProfile: async (profile: { name?: string; service_description: string; skills?: string[] }): Promise<UserProfile> => {
    const { data } = await api.post("/ai/profile", profile);
    return data;
  },

  generateKeywords: async (description: string): Promise<string[]> => {
    const { data } = await api.post("/ai/keywords", { service_description: description });
    return data.keywords;
  },

  enrichLead: async (jobId: number): Promise<{ lead_id: number }> => {
    const { data } = await api.post(`/ai/enrich/${jobId}`);
    return data;
  },

  getLeads: async (status?: string): Promise<EnrichedLead[]> => {
    const params = status ? { status } : {};
    const { data } = await api.get("/ai/leads", { params });
    return data;
  },

  getLead: async (leadId: number): Promise<EnrichedLead> => {
    const { data } = await api.get(`/ai/leads/${leadId}`);
    return data;
  },

  generateOutreach: async (jobId: number): Promise<string> => {
    const { data } = await api.post(`/ai/outreach/${jobId}`);
    return data.outreach_message;
  },

  analyzeLead: async (jobId: number): Promise<LeadAnalysis> => {
    const { data } = await api.post(`/ai/analyze/${jobId}`);
    return data;
  },

  getRecommendations: async (): Promise<{
    hot_leads: Array<{
      id: number;
      title: string;
      detected_company_name: string;
      company_confidence: number;
      client_rating: number | null;
      client_total_spent: string | null;
      budget_type: string | null;
      budget_min: number | null;
      budget_max: number | null;
      posted_at: string | null;
      url: string;
      score: number;
      recommendation: "apply" | "maybe" | "skip";
    }>;
    fresh_opportunities: Array<{
      id: number;
      title: string;
      detected_company_name: string;
      score: number;
      posted_at: string | null;
      url: string;
    }>;
    total_with_company: number;
  }> => {
    const { data } = await api.get("/ai/recommendations");
    return data;
  },

  generateProposal: async (
    jobId: number,
    tone: "professional" | "friendly" | "enthusiastic" = "professional"
  ): Promise<{
    cover_letter: string;
    why_fit: string;
    approach: string;
    timeline: string;
    questions: string[];
    full_proposal: string;
  }> => {
    const { data } = await api.post(`/ai/proposal/${jobId}`, { tone });
    return data;
  },

  generateQuickResponse: async (jobId: number): Promise<string> => {
    const { data } = await api.post(`/ai/quick-response/${jobId}`);
    return data.quick_response;
  },

  getStatus: async (): Promise<{ configured: boolean; model: string; provider: string }> => {
    const { data } = await api.get("/ai/status");
    return data;
  },
};

export const sessionApi = {
  getStatus: async (): Promise<{
    connected: boolean;
    message: string;
    last_connected: string | null;
    needs_refresh?: boolean;
    cookies_count?: number;
  }> => {
    const { data } = await api.get("/session/status");
    return data;
  },

  connect: async (): Promise<{
    success: boolean;
    message: string;
    browser_id?: number;
  }> => {
    const { data } = await api.post("/session/connect");
    return data;
  },

  save: async (): Promise<{
    success: boolean;
    message: string;
    cookies_count?: number;
  }> => {
    const { data } = await api.post("/session/save");
    return data;
  },

  cancel: async (): Promise<{
    success: boolean;
    message: string;
  }> => {
    const { data } = await api.post("/session/cancel");
    return data;
  },

  refresh: async (): Promise<{
    success: boolean;
    message: string;
  }> => {
    const { data } = await api.post("/session/refresh");
    return data;
  },
};


export interface SettingInfo {
  source: "db" | "env" | "unset";
  is_set: boolean;
  is_secret: boolean;
  value: string | null;
  description: string;
}
export type SettingsSnapshot = Record<string, SettingInfo>;

export const settingsApi = {
  getAll: async (): Promise<SettingsSnapshot> => {
    const { data } = await api.get("/settings");
    return data;
  },
  set: async (key: string, value: string): Promise<{ ok: boolean }> => {
    const { data } = await api.put(`/settings/${key}`, { value });
    return data;
  },
  clear: async (key: string): Promise<{ ok: boolean }> => {
    const { data } = await api.delete(`/settings/${key}`);
    return data;
  },
  testGroq: async (): Promise<{ ok: boolean; error?: string; model?: string }> => {
    const { data } = await api.post("/settings/test/groq");
    return data;
  },
};
