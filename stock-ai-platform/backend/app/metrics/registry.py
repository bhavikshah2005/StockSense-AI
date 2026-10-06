"""Supported metrics. Keys match stored fundamental, valuation, and indicator fields."""

from dataclasses import dataclass

from app.metrics import REGISTRY_VERSION

LEVEL = frozenset({">", "<", ">=", "<=", "between", "outside_range"})
LEVEL_AND_CROSS = LEVEL | frozenset({"crosses_above", "crosses_below"})
CROSS = frozenset({"crosses_above", "crosses_below"})


@dataclass(frozen=True)
class MetricDefinition:
    key: str
    name: str
    description: str
    category: str
    unit: str
    operators: frozenset[str]
    source: str
    preference: str
    sector_benchmark: bool = False
    event_kind: str | None = None
    pair: tuple[str, str] | None = None


def _level(
    key: str,
    name: str,
    description: str,
    category: str,
    unit: str,
    source: str,
    preference: str,
    *,
    sector_benchmark: bool = False,
) -> MetricDefinition:
    return MetricDefinition(
        key, name, description, category, unit, LEVEL, source, preference, sector_benchmark, None, None
    )


METRICS: tuple[MetricDefinition, ...] = (
    _level("pe_ratio", "P/E", "Price divided by earnings.", "fundamental", "multiple", "valuation", "lower", sector_benchmark=True),
    _level("pb_ratio", "P/B", "Price divided by book value.", "fundamental", "multiple", "valuation", "lower", sector_benchmark=True),
    _level("peg_ratio", "PEG", "P/E divided by earnings growth.", "fundamental", "multiple", "valuation", "context"),
    _level("ev_to_ebitda", "EV/EBITDA", "Enterprise value divided by EBITDA.", "fundamental", "multiple", "valuation", "lower"),
    _level("ev_to_sales", "EV/Sales", "Enterprise value divided by revenue.", "fundamental", "multiple", "valuation", "lower"),
    _level("dividend_yield", "Dividend yield", "Dividend yield in percentage points.", "fundamental", "percent", "valuation", "higher", sector_benchmark=True),
    _level("roe", "ROE", "Return on equity in percentage points.", "fundamental", "percent", "fundamental", "higher", sector_benchmark=True),
    _level("roce", "ROCE", "Return on capital employed in percentage points.", "fundamental", "percent", "fundamental", "higher", sector_benchmark=True),
    _level("net_margin", "Net profit margin", "Net income relative to revenue, in percentage points.", "fundamental", "percent", "fundamental", "higher", sector_benchmark=True),
    _level("operating_margin", "Operating margin", "Operating profit relative to revenue, in percentage points.", "fundamental", "percent", "fundamental", "higher"),
    _level("gross_margin", "Gross margin", "Gross profit relative to revenue, in percentage points.", "fundamental", "percent", "fundamental", "higher"),
    _level("revenue_growth", "Revenue growth", "Revenue change from the prior period, in percentage points.", "fundamental", "percent", "fundamental", "higher", sector_benchmark=True),
    _level("eps_growth", "EPS growth", "Earnings-per-share change from the prior period, in percentage points.", "fundamental", "percent", "fundamental", "higher"),
    _level("profit_growth", "Profit growth", "Net income change from the prior period, in percentage points.", "fundamental", "percent", "fundamental", "higher"),
    _level("ebitda_growth", "EBITDA growth", "EBITDA change from the prior period, in percentage points.", "fundamental", "percent", "fundamental", "higher"),
    _level("revenue_cagr_3y", "Revenue CAGR, 3 year", "Compound annual revenue growth over about three years.", "fundamental", "percent", "derived_fundamental", "higher"),
    _level("revenue_cagr_5y", "Revenue CAGR, 5 year", "Compound annual revenue growth over about five years.", "fundamental", "percent", "derived_fundamental", "higher"),
    _level("debt_to_equity", "Debt/equity", "Debt relative to equity.", "fundamental", "ratio", "fundamental", "lower", sector_benchmark=True),
    _level("current_ratio", "Current ratio", "Current assets relative to current liabilities.", "fundamental", "ratio", "fundamental", "higher"),
    _level("interest_coverage", "Interest coverage", "Operating profit relative to interest.", "fundamental", "ratio", "fundamental", "higher"),
    _level("free_cash_flow", "Free cash flow", "Free cash flow in rupees.", "fundamental", "inr", "fundamental", "higher"),
    _level("cfo_to_net_profit", "CFO/net profit", "Operating cash flow divided by net income.", "fundamental", "ratio", "derived_fundamental", "context"),
    MetricDefinition("rsi_14", "RSI 14", "Relative strength index from daily closes.", "technical", "index", LEVEL_AND_CROSS, "technical", "context", False, "level", None),
    _level("macd", "MACD", "MACD line from daily closes.", "technical", "price", "technical", "context"),
    _level("sma_100", "SMA 100", "100-session simple moving average of close.", "technical", "price", "technical", "context"),
    _level("macd_histogram", "MACD histogram", "MACD line minus its signal line.", "technical", "price", "technical", "context"),
    _level("sma_20", "SMA 20", "20-session simple moving average of close.", "technical", "price", "technical", "context"),
    _level("sma_50", "SMA 50", "50-session simple moving average of close.", "technical", "price", "technical", "context"),
    _level("sma_200", "SMA 200", "200-session simple moving average of close.", "technical", "price", "technical", "context"),
    _level("ema_20", "EMA 20", "20-session exponential moving average of close.", "technical", "price", "technical", "context"),
    _level("ema_50", "EMA 50", "50-session exponential moving average of close.", "technical", "price", "technical", "context"),
    _level("volatility", "Volatility", "Annualized sample standard deviation of daily log returns, in percentage points.", "technical", "percent", "technical", "context"),
    _level("average_volume", "Average volume", "20-session average volume.", "technical", "shares", "technical", "context"),
    _level("volume", "Volume", "Volume on the latest stored daily bar.", "technical", "shares", "price", "context"),
    _level("distance_from_high_percent", "Distance from 52-week high", "Percent distance of the latest close from the 52-week high.", "technical", "percent", "derived_technical", "context"),
    _level("distance_from_low_percent", "Distance from 52-week low", "Percent distance of the latest close from the 52-week low.", "technical", "percent", "derived_technical", "context"),
    MetricDefinition("sma_20_cross_sma_50", "SMA 20 / SMA 50 cross", "Whether the 20-session average crosses the 50-session average. A single reading is not a cross.", "technical", "event", CROSS, "technical_pair", "context", False, "pair", ("sma_20", "sma_50")),
    MetricDefinition("ema_20_cross_ema_50", "EMA 20 / EMA 50 cross", "Whether the 20-session exponential average crosses the 50-session average. A single reading is not a cross.", "technical", "event", CROSS, "technical_pair", "context", False, "pair", ("ema_20", "ema_50")),
    MetricDefinition("macd_cross_signal", "MACD / signal cross", "Whether the MACD line crosses its signal line. A single reading is not a cross.", "technical", "event", CROSS, "technical_pair", "context", False, "pair", ("macd", "macd_signal")),
)

BY_KEY = {item.key: item for item in METRICS}


def get_metric(key: str) -> MetricDefinition | None:
    return BY_KEY.get(key)


def registry_payload() -> dict[str, object]:
    return {
        "version": REGISTRY_VERSION,
        "metrics": [
            {
                "key": item.key,
                "name": item.name,
                "description": item.description,
                "category": item.category,
                "unit": item.unit,
                "operators": sorted(item.operators),
                "source": item.source,
                "preference": item.preference,
                "sector_benchmark": item.sector_benchmark,
                "event_kind": item.event_kind,
            }
            for item in METRICS
        ],
    }
