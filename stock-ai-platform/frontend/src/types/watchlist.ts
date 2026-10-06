export type WatchlistSummary = {
  id: string;
  name: string;
  description: string | null;
  is_default: boolean;
  stock_count: number;
  contains_stock: boolean | null;
  created_at: string;
  updated_at: string;
};

export type WatchlistListResponse = {
  results: WatchlistSummary[];
};

export type WatchlistQuote = {
  available: boolean;
  delayed: boolean | null;
  source: string | null;
  currency: string | null;
  current_price: string | null;
  previous_close: string | null;
  change: string | null;
  change_percent: string | null;
  market_timestamp: string | null;
  fetched_at: string | null;
};

export type WatchlistEntry = {
  stock_id: string;
  company_name: string;
  symbol: string;
  exchange: string;
  isin: string | null;
  sector: string | null;
  industry: string | null;
  sort_order: number;
  added_at: string;
  quote: WatchlistQuote;
};

export type WatchlistDetail = {
  id: string;
  name: string;
  description: string | null;
  is_default: boolean;
  stock_count: number;
  created_at: string;
  updated_at: string;
  stocks: WatchlistEntry[];
};
