"""SQLAlchemy ORM models for mosques, prayer times, and scrape logs."""

from datetime import datetime, date, time
from typing import List, Optional
from sqlalchemy import String, Text, Numeric, DateTime, Date, Time, Integer, ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSONB


class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass


class Mosque(Base):
    """Mosque entity with location and contact information."""
    
    __tablename__ = "mosques"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    latitude: Mapped[Optional[float]] = mapped_column(Numeric(10, 8), nullable=True)
    longitude: Mapped[Optional[float]] = mapped_column(Numeric(11, 8), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    website: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    keywords: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    region: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship to prayer times
    prayer_times: Mapped[List["PrayerTime"]] = relationship("PrayerTime", back_populates="mosque", cascade="all, delete-orphan")
    
    __table_args__ = (
        UniqueConstraint("name", "region", name="uq_mosque_name_region"),
        Index("idx_mosques_region", "region"),
        Index("idx_mosques_name", "name"),
    )


class PrayerTime(Base):
    """Prayer times and iqamah times for a specific mosque and date."""
    
    __tablename__ = "prayer_times"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    mosque_id: Mapped[int] = mapped_column(Integer, ForeignKey("mosques.id", ondelete="CASCADE"), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    fajr: Mapped[Optional[time]] = mapped_column(Time, nullable=True)
    sunrise: Mapped[Optional[time]] = mapped_column(Time, nullable=True)
    dhuhr: Mapped[Optional[time]] = mapped_column(Time, nullable=True)
    asr: Mapped[Optional[time]] = mapped_column(Time, nullable=True)
    maghrib: Mapped[Optional[time]] = mapped_column(Time, nullable=True)
    isha: Mapped[Optional[time]] = mapped_column(Time, nullable=True)
    iqamah_times: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship back to mosque
    mosque: Mapped["Mosque"] = relationship("Mosque", back_populates="prayer_times")
    
    __table_args__ = (
        UniqueConstraint("mosque_id", "date", name="uq_prayer_time_mosque_date"),
        Index("idx_prayer_times_mosque_date", "mosque_id", "date"),
        Index("idx_prayer_times_date", "date"),
    )


class ScrapeLog(Base):
    """Audit log for scraping jobs."""
    
    __tablename__ = "scrape_logs"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="running")
    region: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    mosques_scraped: Mapped[int] = mapped_column(Integer, default=0)
    errors: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
