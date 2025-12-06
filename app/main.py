"""Main FastAPI application for NADAC Drug Price Inflation Tracker."""
import asyncio
from datetime import date
from typing import Optional, List
from fastapi import FastAPI, Depends, Query, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.services import DrugPriceService
from app.schemas import (
    DrugInflationSummary,
    PriceChange,
    InflationStats,
    TopInflationDrug,
    SearchResult,
    DrugPriceResponse,
    IngestionStatus,
)
from app.ingest import ingest_year, ingest_all_years

app = FastAPI(
    title="NADAC Drug Price Inflation Tracker",
    description="Track drug price inflation using CMS NADAC data",
    version="1.0.0",
)

# Mount static files for the dashboard
try:
    app.mount("/static", StaticFiles(directory="static"), name="static")
except Exception:
    pass  # Static directory might not exist in all environments


@app.get("/")
async def root():
    """Serve the main dashboard."""
    try:
        return FileResponse("static/index.html")
    except Exception:
        return {
            "message": "NADAC Drug Price Inflation Tracker API",
            "docs": "/docs",
            "dashboard": "/static/index.html"
        }


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


# =============================================================================
# Drug Search and Lookup
# =============================================================================

@app.get("/api/drugs/search", response_model=dict)
async def search_drugs(
    q: str = Query(..., min_length=2, description="Search query (drug name or NDC)"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    """Search for drugs by name or NDC code."""
    service = DrugPriceService(db)
    results, total = service.search_drugs(q, limit, offset)
    return {
        "results": results,
        "total": total,
        "limit": limit,
        "offset": offset
    }


@app.get("/api/drugs/{ndc}/history", response_model=List[DrugPriceResponse])
async def get_drug_price_history(
    ndc: str,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db)
):
    """Get price history for a specific drug by NDC."""
    service = DrugPriceService(db)
    prices = service.get_price_history(ndc, start_date, end_date)
    if not prices:
        raise HTTPException(status_code=404, detail=f"No data found for NDC: {ndc}")
    return prices


@app.get("/api/drugs/{ndc}/inflation", response_model=DrugInflationSummary)
async def get_drug_inflation(
    ndc: str,
    db: Session = Depends(get_db)
):
    """Get inflation summary for a specific drug."""
    service = DrugPriceService(db)
    summary = service.get_drug_inflation(ndc)
    if not summary:
        raise HTTPException(status_code=404, detail=f"No data found for NDC: {ndc}")
    return summary


# =============================================================================
# Price Changes
# =============================================================================

@app.get("/api/price-changes", response_model=dict)
async def get_price_changes(
    min_change: Optional[float] = Query(None, description="Minimum percent change"),
    max_change: Optional[float] = Query(None, description="Maximum percent change"),
    start_date: Optional[date] = Query(None, description="Start date filter"),
    end_date: Optional[date] = Query(None, description="End date filter"),
    drug_type: Optional[str] = Query(None, description="Drug type: G (generic), B (brand)"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    """Get price changes with optional filters."""
    service = DrugPriceService(db)
    changes, total = service.get_price_changes(
        min_change_percent=min_change,
        max_change_percent=max_change,
        start_date=start_date,
        end_date=end_date,
        drug_type=drug_type,
        limit=limit,
        offset=offset
    )
    return {
        "results": changes,
        "total": total,
        "limit": limit,
        "offset": offset
    }


# =============================================================================
# Inflation Analytics
# =============================================================================

@app.get("/api/inflation/top", response_model=List[TopInflationDrug])
async def get_top_inflation(
    n: int = Query(20, ge=1, le=100, description="Number of results"),
    direction: str = Query("highest", regex="^(highest|lowest)$"),
    drug_type: Optional[str] = Query(None, description="Drug type: G (generic), B (brand)"),
    min_days: int = Query(30, ge=1, description="Minimum tracking period in days"),
    db: Session = Depends(get_db)
):
    """Get drugs with highest or lowest total inflation."""
    service = DrugPriceService(db)
    ascending = direction == "lowest"
    return service.get_top_inflation(
        top_n=n,
        ascending=ascending,
        drug_type=drug_type,
        min_days=min_days
    )


@app.get("/api/inflation/stats", response_model=InflationStats)
async def get_inflation_stats(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    drug_type: Optional[str] = Query(None, description="Drug type: G (generic), B (brand)"),
    db: Session = Depends(get_db)
):
    """Get overall inflation statistics."""
    service = DrugPriceService(db)
    return service.get_inflation_stats(
        start_date=start_date,
        end_date=end_date,
        drug_type=drug_type
    )


# =============================================================================
# Data Ingestion
# =============================================================================

@app.post("/api/ingest/{year}")
async def trigger_ingestion(
    year: int,
    background_tasks: BackgroundTasks,
    max_records: Optional[int] = Query(None, description="Max records (for testing)"),
    db: Session = Depends(get_db)
):
    """Trigger data ingestion for a specific year."""
    if year < 2019 or year > 2025:
        raise HTTPException(status_code=400, detail="Year must be between 2019 and 2025")

    # Run ingestion in background
    background_tasks.add_task(asyncio.run, ingest_year(year, max_records))

    return {
        "message": f"Ingestion started for year {year}",
        "status": "running"
    }


@app.get("/api/ingest/status", response_model=List[IngestionStatus])
async def get_ingestion_status(
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db)
):
    """Get recent data ingestion status."""
    service = DrugPriceService(db)
    return service.get_ingestion_status(limit)


# =============================================================================
# Data Summary
# =============================================================================

@app.get("/api/summary")
async def get_data_summary(db: Session = Depends(get_db)):
    """Get a summary of available data."""
    from sqlalchemy import func, text
    from app.models import NadacPrice

    total_records = db.query(func.count(NadacPrice.id)).scalar()
    unique_drugs = db.query(func.count(func.distinct(NadacPrice.ndc))).scalar()

    date_range = db.query(
        func.min(NadacPrice.effective_date),
        func.max(NadacPrice.effective_date)
    ).first()

    drug_types = db.execute(text("""
        SELECT classification_for_rate_setting, COUNT(DISTINCT ndc) as count
        FROM nadac_prices
        GROUP BY classification_for_rate_setting
    """)).fetchall()

    return {
        "total_records": total_records,
        "unique_drugs": unique_drugs,
        "date_range": {
            "start": date_range[0] if date_range else None,
            "end": date_range[1] if date_range else None
        },
        "drug_types": {r[0]: r[1] for r in drug_types if r[0]}
    }
