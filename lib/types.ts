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

export type Project = {
  id: string;
  spx_id: string;
  name: string;
  state?: string;
  city: string;
  county: string;
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
