export type MetricDefinition = {
  key: string;
  name: string;
  description: string;
  category: "fundamental" | "technical";
  unit: string;
  operators: string[];
  source: string;
  preference: string;
  sector_benchmark: boolean;
  event_kind: string | null;
};

export type MetricRegistry = {
  version: string;
  metrics: MetricDefinition[];
};

export type ThresholdRecord = {
  id: string;
  metric_key: string;
  scope: string;
  country: string | null;
  sector: string | null;
  stock_id: string | null;
  operator: string;
  basis: string;
  threshold_value: string | null;
  threshold_high: string | null;
  description: string | null;
  is_active: boolean;
  effective_from: string | null;
  effective_to: string | null;
  definition_version: string;
  owned: boolean;
  created_at: string;
  updated_at: string;
};

export type ResolvedThreshold = {
  id: string;
  scope: string;
  operator: string;
  basis: string;
  threshold_value: string | null;
  threshold_high: string | null;
  definition_version: string;
  effective_from: string | null;
  reason: string;
  skipped_scopes: string[];
  user_override: boolean;
};

export type MetricEvaluation = {
  metric_key: string;
  metric_name: string;
  category: string;
  unit: string;
  state: string;
  explanation: string;
  value: string | null;
  previous_value: string | null;
  reference_value: string | null;
  as_of: string | null;
  source: string | null;
  threshold: ResolvedThreshold | null;
};
