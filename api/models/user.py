from datetime import UTC, datetime

from sqlalchemy import DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from api.db.session import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    # NULL means "use the global default from Settings" (api/core/config.py).
    # No admin surface exists yet to edit these per user; see README backlog.
    max_environments: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cpu_limit: Mapped[float | None] = mapped_column(Float, nullable=True)
    mem_limit_mb: Mapped[int | None] = mapped_column(Integer, nullable=True)
