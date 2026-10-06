export type ResearchRun = {
  id: string;
  stock_id: string;
  symbol: string;
  exchange: string;
  status: string;
  analysis_timestamp: string;
  evidence: {
    fundamental?: Array<{ metric_name?: string; state?: string; explanation?: string; as_of?: string | null }>;
    technical?: { category?: string; text?: string; freshness?: string; price_as_of?: string | null } | null;
    patterns?: Array<{ pattern_type?: string; status?: string; as_of?: string | null }>;
    news?: Array<{ title?: string; url?: string; source?: string; published_at?: string; sentiment?: string | null }>;
    gaps?: string[];
  };
  explanation: {
    summary?: string;
    fundamental?: string;
    technical?: string;
    patterns?: string;
    news?: string;
    limitations?: string;
    conflicts?: string[];
  } | null;
  score: {
    version?: string;
    aggregate?: string;
    numeric_score?: null;
    note?: string;
    categories?: Record<string, { status?: string; reason?: string; category?: string }>;
  };
  provider: string;
  model_name: string;
  prompt_version: string;
  scoring_version: string;
  error_message: string | null;
  created_at: string;
};

export type ResearchList = {
  results: ResearchRun[];
  total: number;
  limit: number;
  offset: number;
};

export type ResearchMethodology = {
  prompt_version: string;
  scoring_version: string;
  scoring_note: string;
  ai_note: string;
  configured: boolean;
  provider: string;
};
