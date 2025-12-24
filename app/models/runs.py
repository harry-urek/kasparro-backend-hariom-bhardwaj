"""Enables /stats, observability, and P2 features"""

import uuid
from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ETLRun(Base):
    __tablename__ = "etl_runs"

    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    source_name: Mapped[str] = mapped_column(String, nullable=False)

    status: Mapped[str] = mapped_column(
        String,
        nullable=False,  # running | success | failure
    )

    records_processed: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    error_message: Mapped[str | None] = mapped_column(String, nullable=True)

    # "metadata" attribute name is reserved by SQLAlchemy; use column name metadata with safe attribute.
    meta: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)

    started_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    ended_at: Mapped[DateTime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
