"""Pydantic schemas for API request/response validation."""
from datetime import date, datetime
from decimal import Decimal
from typing import Optional, List
from pydantic import BaseModel, Field


class DrugPriceBase(BaseModel):
    """Base schema for drug price data."""

    ndc: str
    ndc_description: str
    nadac_per_unit: Decimal
    effective_date: date
    pricing_unit: Optional[str] = None
    pharmacy_type_indicator: Optional[str] = None
    otc: Optional[str] = None
    classification_for_rate_setting: Optional[str] = None


class DrugPriceResponse(DrugPriceBase):
    """Response schema for drug price queries."""

    id: int
    as_of_date: date
    created_at: datetime

    class Config:
        from_attributes = True


class PriceChange(BaseModel):
    """Schema for price change data."""

    ndc: str
    ndc_description: str
    current_price: Decimal
    previous_price: Decimal
    current_date: date
    previous_date: date
    percent_change: Decimal
    absolute_change: Decimal
    pricing_unit: Optional[str] = None
    drug_type: Optional[str] = None


class DrugInflationSummary(BaseModel):
    """Summary of inflation for a specific drug."""

    ndc: str
    ndc_description: str
    drug_type: Optional[str] = None
    pricing_unit: Optional[str] = None
    first_price_date: date
    latest_price_date: date
    first_price: Decimal
    latest_price: Decimal
    min_price: Decimal
    max_price: Decimal
    total_percent_change: Decimal
    annualized_percent_change: Optional[Decimal] = None
    price_change_count: int


class TopInflationDrug(BaseModel):
    """Drug with highest/lowest inflation."""

    ndc: str
    ndc_description: str
    drug_type: Optional[str] = None
    first_price: Decimal
    latest_price: Decimal
    total_percent_change: Decimal
    period_days: int


class InflationStats(BaseModel):
    """Overall inflation statistics."""

    total_drugs_tracked: int
    drugs_with_increases: int
    drugs_with_decreases: int
    drugs_unchanged: int
    average_percent_change: Decimal
    median_percent_change: Decimal
    date_range_start: date
    date_range_end: date


class PriceHistory(BaseModel):
    """Price history for a single drug."""

    ndc: str
    ndc_description: str
    history: List[DrugPriceBase]


class SearchResult(BaseModel):
    """Drug search result."""

    ndc: str
    ndc_description: str
    latest_price: Decimal
    latest_date: date
    drug_type: Optional[str] = None


class IngestionStatus(BaseModel):
    """Status of data ingestion."""

    id: int
    started_at: datetime
    completed_at: Optional[datetime] = None
    records_fetched: int
    records_inserted: int
    status: str
    error_message: Optional[str] = None
    year: Optional[int] = None

    class Config:
        from_attributes = True


class PaginatedResponse(BaseModel):
    """Generic paginated response."""

    items: List
    total: int
    page: int
    page_size: int
    total_pages: int
