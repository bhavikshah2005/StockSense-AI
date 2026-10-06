export type StrategyParameter = {
  name: string;
  label: string;
  kind: string;
  minimum: number;
  maximum: number;
  default: number;
  description: string;
};

export type StrategySpec = {
  key: string;
  version: string;
  name: string;
  description: string;
  holds_overnight: boolean;
  direction: string;
  required_data: string;
  entry_rule: string;
  exit_rule: string;
  missing_data: string;
  parameters: StrategyParameter[];
};

export type BacktestSummary = {
  result_basis: string;
  initial_equity: string;
  final_equity: string;
  total_return_inr: string;
  total_return_percent: string | null;
  annualized_return_percent: string | null;
  annualized_return_reason: string | null;
  max_drawdown_percent: string | null;
  max_drawdown_sessions: number | null;
  completed_trades: number;
  winning_trades: number;
  losing_trades: number;
  win_rate_percent: string | null;
  win_rate_reason: string | null;
  average_win_inr: string | null;
  average_loss_inr: string | null;
  average_trade_return_percent: string | null;
  median_trade_return_percent: string | null;
  profit_factor: string | null;
  profit_factor_reason: string | null;
  exposure_percent: string | null;
  turnover: string | null;
  turnover_reason: string | null;
  transaction_costs_inr: string;
  sessions: number;
  benchmark: { available: boolean; reason: string };
};

export type BacktestRun = {
  id: string;
  stock_id: string;
  symbol: string;
  exchange: string;
  strategy_key: string;
  strategy_version: string;
  parameters: Record<string, number>;
  assumptions: Record<string, string | number | null>;
  status: string;
  requested_start: string;
  requested_end: string;
  actual_start: string | null;
  actual_end: string | null;
  initial_capital: string;
  engine_version: string;
  indicator_version: string;
  detector_version: string;
  data_source: string;
  price_basis: string;
  summary: BacktestSummary | null;
  warnings: string[];
  error_detail: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
};

export type BacktestTrade = {
  trade_number: number;
  signal_at: string;
  entry_at: string;
  exit_at: string;
  entry_price: string;
  exit_price: string;
  shares: number;
  entry_charges: string;
  exit_charges: string;
  slippage_cost: string;
  exit_reason: string;
  pnl: string;
  return_percent: string | null;
};

export type EquityPoint = {
  point_at: string;
  equity: string;
  drawdown_percent: string;
  cash: string;
  shares: number;
};

export type CompareResult = {
  left: BacktestRun;
  right: BacktestRun;
  comparable: boolean;
  note: string;
};
