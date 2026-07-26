export interface Job {
  id: number;
  upwork_id: string;
  title: string;
  description: string;
  url: string;
  client_country: string | null;
  client_rating: number | null;
  client_total_spent: string | null;
  client_hires: number | null;
  budget_type: string | null;
  budget_min: number | null;
  budget_max: number | null;
  experience_level: string | null;
  duration: string | null;
  job_type: string | null;
  has_company_mention: boolean;
  detected_company_name: string | null;
  company_confidence: number;
  company_context: string | null;
  search_keywords: string[] | null;
  posted_at: string | null;
  scraped_at: string | null;
  is_bookmarked: boolean;
  is_hidden: boolean;
  notes: string | null;
  created_at: string;
}

export interface JobListResponse {
  jobs: Job[];
  total: number;
  page: number;
  per_page: number;
  has_company_mention_count: number;
}

export interface SearchRequest {
  keywords: string[];
  search_type: "AND" | "OR";
  category?: string;
  experience_level?: string;
  budget_min?: number;
  budget_max?: number;
  client_hires_min?: number;
  only_company_mentions?: boolean;
  // 0 = scrape until Upwork runs out (hard-capped at 100 pages / ~1000 jobs).
  max_pages?: number;
}

export interface SearchResponse {
  message: string;
  total_found: number;
  with_company_mention: number;
  keywords: string[];
}

export interface SearchQuery {
  id: number;
  keywords: string[];
  search_type: string;
  filters: Record<string, unknown> | null;
  is_active: boolean;
  run_count: number;
  last_run_at: string | null;
  created_at: string;
}

export interface Stats {
  total_jobs: number;
  jobs_with_company: number;
  bookmarked_jobs: number;
}

export interface UserProfile {
  id: number;
  name: string | null;
  service_description: string;
  skills: string[] | null;
  generated_keywords: string[] | null;
}

export interface EnrichedLead {
  id: number;
  job_id: number;
  company_name: string;
  website: string | null;
  emails: string[];
  phones: string[];
  linkedin: string | null;
  twitter: string | null;
  instagram: string | null;
  facebook: string | null;
  address: string | null;
  description: string | null;
  lead_score: number;
  status: string;
  enriched_at: string | null;
}

export interface LeadAnalysis {
  score: number;
  reasons: string[];
  recommendation: "apply" | "skip" | "maybe";
}
