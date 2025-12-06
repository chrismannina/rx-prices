"""SQLAlchemy models for NADAC data."""
from datetime import datetime, date
from decimal import Decimal
from sqlalchemy import Column, Integer, String, Numeric, Date, DateTime, Text
from app.database import Base


class NadacPrice(Base):
    """Model for NADAC drug pricing data."""

    __tablename__ = "nadac_prices"

    id = Column(Integer, primary_key=True, index=True)
    ndc = Column(String(11), nullable=False, index=True)
    ndc_description = Column(Text, nullable=False)
    nadac_per_unit = Column(Numeric(12, 6), nullable=False)
    effective_date = Column(Date, nullable=False, index=True)
    pricing_unit = Column(String(10))
    pharmacy_type_indicator = Column(String(5))
    otc = Column(String(1))
    explanation_code = Column(String(10))
    classification_for_rate_setting = Column(String(5))
    corresponding_generic_drug_nadac = Column(Numeric(12, 6))
    corresponding_generic_drug_effective_date = Column(Date)
    as_of_date = Column(Date, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class IngestionLog(Base):
    """Model for tracking data ingestion runs."""

    __tablename__ = "ingestion_log"

    id = Column(Integer, primary_key=True, index=True)
    started_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    completed_at = Column(DateTime)
    records_fetched = Column(Integer, default=0)
    records_inserted = Column(Integer, default=0)
    status = Column(String(20), default="running")
    error_message = Column(Text)
    year = Column(Integer)
