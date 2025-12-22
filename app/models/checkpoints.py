"""Powers incremental ingestion + resume-on-failure"""

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ETLCheckpoint(Base):
    __tablename__ = "etl_checkpoints"

    source_name: Mapped[str] = mapped_column(
        String,
        primary_key=True,
    )

    last_updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
