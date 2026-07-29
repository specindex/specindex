export type ProjectStatus =
  | "planning"
  | "bidding"
  | "design"
  | "under_construction"
  | "permitting";

export type ProjectType =
  | "office"
  | "mixed_use"
  | "hospitality"
  | "healthcare"
  | "education"
  | "industrial"
  | "retail"
  | "civic"
  | "multifamily"
  | "airport"
  | "other";

export type ProjectSource = {
  title: string;
  url: string;
};

export type ProjectScore = {
  total: number;
  value: number;
  recency: number;
  news: number;
} | null;

export type ProjectTimelineEvent = {
  event_type: string;
  event_date: string | null;
  source_name: string;
  source_url: string | null;
};

export type ProjectProvenance = {
  source_name: string;
  source_url: string | null;
  is_primary: boolean;
};

export type ProjectNewsItem = {
  title: string;
  url: string;
  source_name: string | null;
  published_at: string | null;
};

// "confirmed" = two independent Gemini passes agreed; "reported" = passes
// disagreed or only one pass ran (shown with the disagreement, not
// resolved silently); "unconfirmed" = neither pass could find it. See
// scripts/enrich-project-details.py.
export type EnrichmentConfidence = "confirmed" | "reported" | "unconfirmed";

export type EnrichmentFact = {
  field_key: string;
  label: string;
  value: string;
  confidence: EnrichmentConfidence;
  sources: string | null;
};

export type ProjectEnrichment = {
  executive_brief: EnrichmentFact[];
  csi_scope: EnrichmentFact[];
  team: EnrichmentFact[];
  permit: EnrichmentFact[];
  contact: EnrichmentFact[];
  // When the enrichment pipeline last ran against this project (real
  // project_enrichment_checks.checked_at, not a fabricated freshness
  // claim) -- null if it's never been checked.
  checked_at: string | null;
};

export type ProjectDocumentFile = {
  title: string;
  url: string;
  content_type: string | null;
};

export type Project = {
  id: string;
  spx_id: string;
  name: string;
  state?: string;
  city: string;
  county: string;
  latitude?: number | null;
  longitude?: number | null;
  status: ProjectStatus | string;
  project_type: ProjectType | string;
  estimated_value_usd: number | null;
  square_footage: number | null;
  owner: string;
  architect: string;
  general_contractor: string;
  opened_or_announced_date?: string;
  description: string;
  key_specs: string[];
  mentioned_brands: string[];
  competitor_watch: string[];
  sources: ProjectSource[];
  open_for: string;
  score: ProjectScore;
  timeline: ProjectTimelineEvent[];
  provenance: ProjectProvenance[];
  news: ProjectNewsItem[];
  first_seen_at?: string | null;
  document_count?: number;
  has_documents?: boolean;
  // Detail-endpoint only (GET /v1/projects/{id}) -- not present on list-page
  // rows, which don't fetch this to keep list pagination cheap.
  enrichment?: ProjectEnrichment;
  documents?: ProjectDocumentFile[];
};

export type ProjectCorpus = {
  generated_at: string;
  geography: string;
  capture_method?: string;
  date_range?: string;
  states_covered?: string[];
  projects: Project[];
  stats?: {
    total: number;
    opened_last_3_months?: number;
    opened_last_90_days?: number;
    states?: number;
  };
  notes?: string;
};
