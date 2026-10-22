export interface HealthRecord {
  state: string;
  district: string;
  year: string | null;
  month?: string | null;
  source: string;
  indicator: string;
  parameter?: string | null;
  category?: string | null;
  value: number | null;
  geographic_level?: string | null;
  report_type?: string | null;
  indicator_type?: string | null;
  unit?: string | null;
  display_label?: string | null;
  evidence_id?: string | null;
  location?: string | null;
}

export interface Stats {
  total_records: number;
  indicators: number;
  states: number;
  districts: number;
  year_min: string | null;
  year_max: string | null;
  sources?: Record<string, number>;
}

export interface Filters {
  states: string[];
  districts: string[];
  years: string[];
  sources: string[];
}

export interface Scheme {
  id: string;
  name: string;
  official_url: string;
  authority?: string | null;
  summary: string | null;
  eligibility: string | null;
  benefits: string | null;
  how_to_apply: string | null;
  last_verified: string | null;
}

export interface EvidenceSummary {
  record_count: number;
  distinct_indicators: string[];
  distinct_locations: string[];
  distinct_years: string[];
  sources: string[];
  statistics?: {
    min: number | null;
    max: number | null;
    mean: number | null;
  } | null;
  methodology: string;
}

export interface ChatResponse {
  answer: string;
  answer_type: "ai_generated" | "dataset_only" | "no_data" | "comparison" | "trend" | "single_record" | "multiple_records";
  intent?: string;
  mode: string;
  model_enabled?: boolean;
  model_available?: boolean;
  inference_mode?: string;
  fallback_used?: boolean;
  fallback_reason?: string | null;
  evidence_count?: number;
  records: HealthRecord[];
  evidence_summary?: EvidenceSummary | null;
  follow_ups?: string[];
  filters_used?: Record<string, string | null>;
  disclaimer?: string;
}

export interface HealthStatus {
  status: string;
  records: number;
  model_loaded: boolean;
  model_enabled?: boolean;
  model_available?: boolean;
  device: string;
  precision?: string;
  model_error?: string | null;
  diagnostic?: string | null;
  base_model_id?: string;
}

export interface Query {
  q?: string;
  state?: string;
  district?: string;
  year?: string;
  indicator?: string;
  source?: string;
  limit?: number;
}

export interface ExplorerQuery {
  q?: string;
  state?: string;
  district?: string;
  year?: string;
  source?: string;
  indicator?: string;
  geographic_level?: string;
  category?: string;
  page: number;
  page_size: number;
  sort_by?: string;
  sort_order?: "asc" | "desc";
}

export interface ExplorerResponse {
  total_records: number;
  page: number;
  page_size: number;
  total_pages: number;
  records: HealthRecord[];
}

export interface IndicatorMeta {
  indicator: string;
  label: string;
  indicator_type: string;
  unit: string;
  source: string;
  category: string;
  years: string[];
  geographic_levels: string[];
  records_count: number;
}

export interface LocationMeta {
  id: string;
  name: string;
  state: string;
  label: string;
}

export interface WorkspaceCompareRequest {
  indicator: string;
  locations: string[];
  year?: string;
  source?: string;
  geographic_scope?: string;
}

export interface WorkspaceCompareResponse {
  indicator: string;
  canonical_indicator?: string;
  display_label?: string;
  found: boolean;
  year?: string | null;
  available_years?: string[];
  source?: string | null;
  available_sources?: string[];
  records: HealthRecord[];
  matched_locations?: string[];
  missing_locations?: string[];
  statistics?: {
    count: number;
    min: number;
    max: number;
    mean: number;
    median: number;
    range: number;
  } | null;
  methodology: string;
  reproducibility_signature?: string;
}

export interface SavedAnalysis {
  id: string;
  title: string;
  createdAt: string;
  indicator: string;
  locations: string[];
  year?: string;
  source?: string;
  response: WorkspaceCompareResponse;
}
