"""Database enums.

Values are stored as PostgreSQL enum labels, not as undocumented integers.
"""

import enum

from sqlalchemy import Enum


class AlertOperator(enum.StrEnum):
    """Comparison used by alerts and default metric thresholds."""

    GT = ">"
    LT = "<"
    GTE = ">="
    LTE = "<="
    EQ = "="
    BETWEEN = "between"
    OUTSIDE_RANGE = "outside_range"
    CROSSES_ABOVE = "crosses_above"
    CROSSES_BELOW = "crosses_below"


class ThresholdType(enum.StrEnum):
    """How an alert threshold should be interpreted."""

    ABSOLUTE = "absolute"
    SECTOR_RELATIVE = "sector_relative"
    PERCENTAGE = "percentage"
    USER_DEFINED = "user_defined"


class MetricScope(enum.StrEnum):
    """How widely a default metric threshold applies."""

    GLOBAL = "global"
    COUNTRY = "country"
    SECTOR = "sector"
    USER = "user"


class Sentiment(enum.StrEnum):
    """Direction of a news-sentiment result. Uncertain means the classifier declined to choose."""

    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"
    UNCERTAIN = "uncertain"


class Importance(enum.StrEnum):
    """Editorial importance of a news article. Not a numeric rank."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class RiskLevel(enum.StrEnum):
    """Qualitative risk label on an AI analysis. Not a calculated risk metric."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class AnalysisSignal(enum.StrEnum):
    """AI-generated stance. This is stored analysis, not an order instruction."""

    BUY = "BUY"
    HOLD = "HOLD"
    SELL = "SELL"


def _enum_values(enum_cls: type[enum.Enum]) -> list[str]:
    return [member.value for member in enum_cls]


def pg_enum(enum_cls: type[enum.Enum], name: str) -> Enum:
    """PostgreSQL enum that persists the member value."""
    return Enum(
        enum_cls,
        name=name,
        native_enum=True,
        values_callable=_enum_values,
    )


ALERT_OPERATOR = pg_enum(AlertOperator, "alert_operator")
THRESHOLD_TYPE = pg_enum(ThresholdType, "threshold_type")
METRIC_SCOPE = pg_enum(MetricScope, "metric_scope")
SENTIMENT = pg_enum(Sentiment, "sentiment_label")
IMPORTANCE = pg_enum(Importance, "importance_level")
RISK_LEVEL = pg_enum(RiskLevel, "risk_level")
ANALYSIS_SIGNAL = pg_enum(AnalysisSignal, "analysis_signal")
