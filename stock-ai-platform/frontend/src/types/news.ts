export type NewsStockLink = {
  stock_id: string;
  symbol: string;
  exchange: string;
  company_name: string;
  match_method: string;
};

export type NewsCard = {
  id: string;
  title: string;
  summary: string | null;
  source: string;
  url: string;
  author: string | null;
  published_at: string;
  ingested_at: string;
  language: string | null;
  sentiment: string | null;
  sentiment_explanation: string | null;
  stocks: NewsStockLink[];
};

export type NewsList = {
  results: NewsCard[];
  total: number;
  limit: number;
  offset: number;
};

export type NewsStatus = {
  configured: boolean;
  provider: string;
  last_success_at: string | null;
  last_status: string | null;
  last_error: string | null;
  stale: boolean;
  message: string;
};

export type NewsFacets = {
  sources: string[];
  sectors: string[];
};
