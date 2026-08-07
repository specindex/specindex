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
  /** Always 0. Removed from the composite -- it fired on 5 projects out of
   *  591,618. Kept on the type only so older payloads still parse. */
  news: number;
  /** Spec position: 0-45, the largest component and the only one that
   *  reflects what SpecIndex sells. Currently non-zero on ~0.3% of the
   *  corpus, so the UI must say when it is absent rather than showing a
   *  silent low number. */
  position?: number;
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
  document_type: string;
};

/** A manufacturer named in a project's specification, with the sentence that
 *  says so and the page it is on.
 *
 *  NOT a substitution ruling. The rows come from a table called
 *  substitution_rulings, but every one carries ruling='pending' and
 *  confidence='reported' -- nothing was adjudicated. This says what the
 *  specification NAMES, which is a narrower claim and the only one supportable.
 */
export type SpecCitation = {
  manufacturer: string;
  product?: string | null;
  csi_division?: string | null;
  csi_section?: string | null;
  page_number: number;
  quoted_text: string;
  source_url?: string | null;
  ruling?: string | null;
  confidence?: string | null;
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
  spec_citations?: SpecCitation[];
  // True when GET /v1/projects/{id} returned the public teaser (no signed-in
  // Firebase session) rather than the full record -- api/main.py's
  // _to_public_teaser. Value/GC/architect/owner/brands/sources/exact
  // coordinates are all omitted in that case, not just empty.
  gated?: boolean;
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
