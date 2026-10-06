export type EvidenceCategory =
  | "bullish_evidence"
  | "bearish_evidence"
  | "mixed_evidence"
  | "no_clear_direction"
  | "insufficient_data";

export type PatternStatus = "developing" | "confirmed" | "invalidated" | "completed" | "uncertain" | "insufficient_data";

export type TechnicalStock = {
  id: string;
  symbol: string;
  exchange: string;
  company_name: string;
};

export type IndicatorBlock = {
  rsi_14: string | null;
  macd: string | null;
  macd_signal: string | null;
  macd_histogram: string | null;
  sma_20: string | null;
  sma_50: string | null;
  sma_100: string | null;
  sma_200: string | null;
  ema_20: string | null;
  ema_50: string | null;
  volatility: string | null;
  average_volume: string | null;
  volume: number | null;
  week52_high: string | null;
  week52_low: string | null;
  distance_from_high_percent: string | null;
  distance_from_low_percent: string | null;
  performance: Record<string, string | null>;
  as_of: string | null;
};

export type SeriesPoint = {
  timestamp: string;
  close: string;
  sma_20: string | null;
  sma_50: string | null;
  volume: number | null;
};

export type PivotPoint = {
  timestamp: string;
  confirmed_at: string;
  kind: string;
  price: string;
};

export type BoundaryPoint = {
  timestamp: string;
  price: string;
};

export type PatternBlock = {
  pattern_type: string;
  direction: string;
  status: PatternStatus;
  start_timestamp: string;
  end_timestamp: string;
  levels: Record<string, string>;
  boundaries: Record<string, BoundaryPoint[]>;
  pivots: PivotPoint[];
  confirmation_met: boolean;
  confirmation_timestamp: string | null;
  invalidation: string;
  evidence: string;
  limitations: string[];
  quality: string;
  detector_version: string;
  definition: string;
};

export type ZoneBlock = {
  kind: string;
  lower: string;
  upper: string;
  tests: number;
  last_test: string | null;
  status: string;
  method: string;
};

export type BreakoutBlock = {
  source: string;
  side: string;
  status: string;
  boundary: string;
  confirmation_met: boolean;
  volume_evidence: string;
  missing: string[];
};

export type ConclusionBlock = {
  category: EvidenceCategory;
  text: string;
  conflicts: string[];
  invalidation: string[];
};

export type TechnicalAnalysis = {
  stock: TechnicalStock;
  interval: string;
  freshness: "current" | "stale" | "insufficient";
  price_as_of: string | null;
  calculated_at: string;
  indicators: IndicatorBlock;
  series: SeriesPoint[];
  patterns: PatternBlock[];
  zones: ZoneBlock[];
  breakouts: BreakoutBlock[];
  conclusion: ConclusionBlock;
  limitations: string[];
  indicator_version: string;
  detector_version: string;
};
