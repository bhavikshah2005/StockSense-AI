export type PortfolioSummary = {
  id: string;
  name: string;
  description: string | null;
  currency: string;
  contributed: string;
  cash: string;
  holding_count: number;
  archived_at: string | null;
  created_at: string;
  updated_at: string;
};

export type Holding = {
  stock_id: string;
  symbol: string;
  exchange: string;
  company_name: string;
  sector: string | null;
  quantity: string;
  average_cost: string;
  cost_basis: string;
  realized_pnl: string;
  last_price: string | null;
  market_value: string | null;
  unrealized_pnl: string | null;
  unrealized_pnl_percent: string | null;
  price_timestamp: string | null;
  price_state: string;
  delayed: boolean | null;
  delay_minutes: number | null;
};

export type AllocationSlice = {
  symbol?: string | null;
  stock_id?: string | null;
  sector?: string | null;
  market_value: string;
  weight_percent: string;
};

export type Valuation = {
  portfolio_id: string;
  currency: string;
  cash: string;
  contributed: string;
  cost_basis: string;
  market_value: string | null;
  realized_pnl: string;
  unrealized_pnl: string | null;
  total_pnl: string | null;
  valuation_complete: boolean;
  holdings_only: boolean;
  basis: string;
  benchmark: null;
  benchmark_note: string;
  as_of: string;
  holdings: Holding[];
  allocation: {
    status: string;
    by_stock: AllocationSlice[];
    by_sector: AllocationSlice[];
    unpriced_symbols: string[];
  };
};

export type PortfolioTransaction = {
  id: string;
  portfolio_id: string;
  stock_id: string;
  symbol: string;
  exchange: string;
  side: string;
  quantity: string;
  price: string;
  charges: string;
  traded_at: string;
  note: string | null;
};

export type CashMovement = {
  id: string;
  kind: string;
  amount: string;
  occurred_at: string;
  note: string | null;
};

export type HistoryPoint = { date: string; holdings_value: string };

export type PortfolioHistory = {
  status: string;
  message: string;
  points: HistoryPoint[];
};

export type RiskSettings = {
  capital_inr: string | null;
  max_risk_inr: string | null;
  max_risk_percent: string | null;
  max_allocation_percent: string | null;
  max_shares: number | null;
};

export type SizeResult = {
  quantity: number;
  position_value: string;
  per_share_risk: string;
  total_risk: string;
  capital_utilization_percent: string;
  binding_constraint: string;
  risk_amount: string;
  assumptions: string;
  warning: string;
};
