export type FundamentalMetadata = {
  currency: string;
  source: string | null;
  data_as_of: string | null;
  is_available: boolean;
  is_stale: boolean;
  filing_date_known: boolean;
  supplemented_from_period?: string | null;
};

export type FundamentalPeriod = {
  fiscal_period: string;
  fiscal_period_type: string;
  report_date: string;
  filing_date: string | null;
};

export type FundamentalMetrics = {
  revenue: string | null;
  revenue_growth: string | null;
  ebitda: string | null;
  ebitda_growth: string | null;
  operating_profit: string | null;
  net_income: string | null;
  profit_growth: string | null;
  eps: string | null;
  eps_growth: string | null;
  book_value_per_share: string | null;
  roe: string | null;
  roce: string | null;
  gross_margin: string | null;
  operating_margin: string | null;
  net_margin: string | null;
  debt_to_equity: string | null;
  current_ratio: string | null;
  interest_coverage: string | null;
  free_cash_flow: string | null;
  operating_cash_flow: string | null;
  cfo_to_net_profit: string | null;
  revenue_cagr_3y: string | null;
  revenue_cagr_5y: string | null;
};

export type FundamentalReport = {
  stock: { id: string; symbol: string; exchange: string; company_name: string };
  data: FundamentalMetrics;
  period: FundamentalPeriod | null;
  metadata: FundamentalMetadata;
};

export type ValuationMetrics = {
  market_price: string | null;
  market_cap: string | null;
  enterprise_value: string | null;
  pe_ratio: string | null;
  pb_ratio: string | null;
  peg_ratio: string | null;
  ev_to_ebitda: string | null;
  ev_to_sales: string | null;
  dividend_yield: string | null;
};

export type ValuationSnapshot = {
  stock: { id: string; symbol: string; exchange: string; company_name: string };
  data: ValuationMetrics;
  snapshot_at: string | null;
  metadata: FundamentalMetadata;
};

export type SectorMetric = {
  metric: string;
  stock_value: string | null;
  benchmark_value: string | null;
  difference: string | null;
};

export type SectorComparison = {
  stock: { id: string; symbol: string; exchange: string; company_name: string };
  sector: string | null;
  calculation_date: string | null;
  source: string | null;
  methodology: string | null;
  metrics: SectorMetric[];
  benchmark_available: boolean;
};
