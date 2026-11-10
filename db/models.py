from datetime import datetime
from sqlalchemy import String, Integer, Float, DateTime, JSON, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    target: Mapped[str] = mapped_column(String(255), index=True)       # container/pod name
    alert_type: Mapped[str] = mapped_column(String(64))                 # cpu_high, mem_high, restart_loop, crashloop...
    status: Mapped[str] = mapped_column(String(16), default="open")     # open | resolved
    breach_count: Mapped[int] = mapped_column(Integer, default=1)

    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    raw_metrics: Mapped[dict] = mapped_column(JSON, default=dict)
    diagnosis: Mapped[str | None] = mapped_column(String, nullable=True)
    notified: Mapped[bool] = mapped_column(default=False)