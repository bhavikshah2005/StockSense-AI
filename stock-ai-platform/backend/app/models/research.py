"""User-owned research runs.

The narrative, when present, is a model explanation of stored evidence.
It is not a price, a forecast, or a trade instruction. The older `ai_analysis`
table is not used for these runs.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, Index, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.mixins import CreatedAtMixin, UUIDPrimaryKeyMixin, uuid_fk

if TYPE_CHECKING:
    from app.models.stock import Stock
    from app.models.user import User


class ResearchAnalysis(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    __tablename__ = "research_analyses"
    __table_args__ = (
        Index("ix_research_analyses_user_created", "user_id", "created_at"),
        Index("ix_research_analyses_user_stock_created", "user_id", "stock_id", "created_at"),
    )

    user_id: Mapped[uuid.UUID] = uuid_fk("users.id", ondelete="CASCADE")
    stock_id: Mapped[uuid.UUID] = uuid_fk("stocks.id", ondelete="CASCADE")
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    analysis_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    explanation: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    score: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    model_name: Mapped[str] = mapped_column(String(128), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(32), nullable=False)
    scoring_version: Mapped[str] = mapped_column(String(32), nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text)

    user: Mapped[User] = relationship()
    stock: Mapped[Stock] = relationship()
