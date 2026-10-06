export type AlertRecord = {
  id: string;
  stock_id: string;
  symbol: string;
  exchange: string;
  company_name: string;
  category: string;
  metric: string;
  operator: string;
  threshold_type: string;
  threshold_value: string | null;
  threshold_high: string | null;
  pattern_type: string | null;
  pattern_status: string | null;
  percent_interval: string | null;
  repeat_mode: string;
  status: string;
  armed: boolean;
  note: string | null;
  last_evaluated_at: string | null;
  last_data_status: string | null;
  last_value: string | null;
  created_at: string;
  updated_at: string;
};

export type AlertList = {
  results: AlertRecord[];
  total: number;
  limit: number;
  offset: number;
};

export type AlertEventRecord = {
  id: string;
  alert_id: string;
  stock_id: string;
  triggered_value: string;
  previous_value: string | null;
  threshold_value: string;
  triggered_at: string;
  observed_at: string | null;
  message: string;
  data_status: string;
  source: string | null;
};

export type NotificationRecord = {
  id: string;
  alert_id: string;
  stock_id: string;
  symbol: string;
  message: string;
  triggered_at: string;
  read_at: string | null;
  created_at: string;
};

export type NotificationList = {
  results: NotificationRecord[];
  total: number;
  unread: number;
  limit: number;
  offset: number;
};

export type NotificationPreferences = {
  in_app_enabled: boolean;
};

export type CatalogMetric = {
  key: string;
  name: string;
  operators: string[];
  unit: string;
  intervals?: string[];
  sector_benchmark?: boolean;
  event_kind?: string | null;
};

export type AlertCatalog = {
  price: { metrics: CatalogMetric[] };
  fundamental: CatalogMetric[];
  technical: CatalogMetric[];
  pattern: { types: string[]; statuses: string[]; description: string };
  repeat_modes: string[];
};

export type AlertPreview = {
  alert_id: string;
  preview: boolean;
  state: string;
  explanation: string;
  value: string | null;
  previous_value: string | null;
  reference_value: string | null;
  observed_at: string | null;
  source: string | null;
  would_trigger: boolean;
};
