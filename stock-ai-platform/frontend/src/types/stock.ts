export type StockSearchResult = {
  id: string;
  symbol: string;
  company_name: string;
  exchange: string;
  sector: string | null;
  industry: string | null;
  currency: string;
  country: string;
  country_name: string;
  isin: string | null;
};

export type StockSearchResponse = {
  query: string;
  results: StockSearchResult[];
};

export type StockDetail = StockSearchResult;

export type HistoryBar = {
  timestamp: string;
  open: string;
  high: string;
  low: string;
  close: string;
  adjusted_close: string | null;
  volume: number;
};

export type HistoryPerformance = {
  start_price: string;
  end_price: string;
  change: string;
  change_percent: string;
};

export type HistoryResponse = {
  stock: {
    id: string;
    symbol: string;
    company_name: string;
    exchange: string;
    currency: string;
  };
  interval: string;
  range: string | null;
  start_date: string;
  end_date: string;
  market_timestamp: string | null;
  fetched_at: string;
  data: HistoryBar[];
  performance: HistoryPerformance | null;
  period_high: string | null;
  period_low: string | null;
};

export type MarketStatus = {
  exchange: string;
  status: string;
  observed_at: string;
  source: string;
};

export type Quote = {
  stock_id: string;
  symbol: string;
  exchange: string;
  currency: string;
  current_price: string;
  previous_close: string | null;
  change: string | null;
  change_percent: string | null;
  open: string | null;
  high: string | null;
  low: string | null;
  volume: number | null;
  market_timestamp: string;
  fetched_at: string;
  delayed: boolean;
  delay_minutes: number | null;
};
