"""Stored AI analysis.

Scores and the signal are model output. They are not the source of truth for
prices, fundamentals, or position size. `reasons` and `risks` are JSON arrays
of strings.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Index, Numeric, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import ANALYSIS_SIGNAL, RISK_LEVEL, AnalysisSignal, RiskLevel
from app.models.mixins import CreatedAtMixin, UUIDPrimaryKeyMixin, uuid_fk

if TYPE_CHECKING:
    from app.models.stock import Stock

SCORE = Numeric(8, 4)


class AiAnalysis(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    __tablename__ = "ai_analysis"
    __table_args__ = (
        Index(
            "ix_ai_analysis_stock_id_analysis_timestamp",
            "stock_id",
            "analysis_timestamp",
        ),
    )

    stock_id: Mapped[uuid.UUID] = uuid_fk("stocks.id", ondelete="CASCADE")
    analysis_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    signal: Mapped[AnalysisSignal] = mapped_column(ANALYSIS_SIGNAL, nullable=False)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    risk_level: Mapped[RiskLevel | None] = mapped_column(RISK_LEVEL)
    fundamental_score: Mapped[Decimal | None] = mapped_column(SCORE)
    valuation_score: Mapped[Decimal | None] = mapped_column(SCORE)
    technical_score: Mapped[Decimal | None] = mapped_column(SCORE)
    growth_score: Mapped[Decimal | None] = mapped_column(SCORE)
    news_score: Mapped[Decimal | None] = mapped_column(SCORE)
    overall_score: Mapped[Decimal | None] = mapped_column(SCORE)
    summary: Mapped[str | None] = mapped_column(Text)
    reasons: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
    )
    risks: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
    )
    model_name: Mapped[str] = mapped_column(String(128), nullable=False)

    stock: Mapped[Stock] = relationship(back_populates="ai_analyses")
