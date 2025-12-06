"""Business logic services for drug price inflation tracking."""
from datetime import date, timedelta
from decimal import Decimal
from typing import List, Optional, Tuple
from sqlalchemy import text, func, desc, asc
from sqlalchemy.orm import Session

from app.models import NadacPrice, IngestionLog
from app.schemas import (
    DrugInflationSummary,
    PriceChange,
    InflationStats,
    TopInflationDrug,
    SearchResult,
)


class DrugPriceService:
    """Service for drug price queries and inflation calculations."""

    def __init__(self, db: Session):
        self.db = db

    def search_drugs(
        self,
        query: str,
        limit: int = 20,
        offset: int = 0
    ) -> Tuple[List[SearchResult], int]:
        """Search for drugs by name or NDC."""
        search_term = f"%{query.upper()}%"

        # Get distinct drugs with their latest price
        subquery = (
            self.db.query(
                NadacPrice.ndc,
                NadacPrice.ndc_description,
                NadacPrice.nadac_per_unit,
                NadacPrice.effective_date,
                NadacPrice.classification_for_rate_setting,
                func.row_number()
                .over(
                    partition_by=NadacPrice.ndc,
                    order_by=desc(NadacPrice.effective_date)
                )
                .label("rn")
            )
            .filter(
                (NadacPrice.ndc.ilike(search_term)) |
                (NadacPrice.ndc_description.ilike(search_term))
            )
            .subquery()
        )

        # Count total
        count_query = (
            self.db.query(func.count(func.distinct(NadacPrice.ndc)))
            .filter(
                (NadacPrice.ndc.ilike(search_term)) |
                (NadacPrice.ndc_description.ilike(search_term))
            )
        )
        total = count_query.scalar()

        # Get results
        results = (
            self.db.query(subquery)
            .filter(subquery.c.rn == 1)
            .offset(offset)
            .limit(limit)
            .all()
        )

        return [
            SearchResult(
                ndc=r.ndc,
                ndc_description=r.ndc_description,
                latest_price=r.nadac_per_unit,
                latest_date=r.effective_date,
                drug_type=r.classification_for_rate_setting
            )
            for r in results
        ], total

    def get_price_history(
        self,
        ndc: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> List[NadacPrice]:
        """Get price history for a specific drug by NDC."""
        query = self.db.query(NadacPrice).filter(NadacPrice.ndc == ndc)

        if start_date:
            query = query.filter(NadacPrice.effective_date >= start_date)
        if end_date:
            query = query.filter(NadacPrice.effective_date <= end_date)

        return query.order_by(asc(NadacPrice.effective_date)).all()

    def get_drug_inflation(self, ndc: str) -> Optional[DrugInflationSummary]:
        """Calculate inflation summary for a specific drug."""
        prices = self.get_price_history(ndc)
        if not prices:
            return None

        first_price = prices[0]
        latest_price = prices[-1]

        first_val = float(first_price.nadac_per_unit)
        latest_val = float(latest_price.nadac_per_unit)

        if first_val > 0:
            total_change = ((latest_val - first_val) / first_val) * 100
        else:
            total_change = 0

        # Calculate annualized change
        days_between = (latest_price.effective_date - first_price.effective_date).days
        if days_between > 0 and first_val > 0:
            years = days_between / 365.25
            if years > 0:
                annualized = ((latest_val / first_val) ** (1 / years) - 1) * 100
            else:
                annualized = None
        else:
            annualized = None

        return DrugInflationSummary(
            ndc=ndc,
            ndc_description=first_price.ndc_description,
            drug_type=first_price.classification_for_rate_setting,
            pricing_unit=first_price.pricing_unit,
            first_price_date=first_price.effective_date,
            latest_price_date=latest_price.effective_date,
            first_price=Decimal(str(first_val)),
            latest_price=Decimal(str(latest_val)),
            min_price=min(Decimal(str(float(p.nadac_per_unit))) for p in prices),
            max_price=max(Decimal(str(float(p.nadac_per_unit))) for p in prices),
            total_percent_change=Decimal(str(round(total_change, 2))),
            annualized_percent_change=Decimal(str(round(annualized, 2))) if annualized else None,
            price_change_count=len(prices)
        )

    def get_price_changes(
        self,
        min_change_percent: Optional[float] = None,
        max_change_percent: Optional[float] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        drug_type: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> Tuple[List[PriceChange], int]:
        """Get price changes with optional filters."""
        query = """
            WITH ranked_prices AS (
                SELECT
                    ndc,
                    ndc_description,
                    nadac_per_unit,
                    effective_date,
                    pricing_unit,
                    classification_for_rate_setting,
                    LAG(nadac_per_unit) OVER (PARTITION BY ndc ORDER BY effective_date) as prev_price,
                    LAG(effective_date) OVER (PARTITION BY ndc ORDER BY effective_date) as prev_date
                FROM nadac_prices
                WHERE 1=1
                {date_filter}
                {type_filter}
            )
            SELECT
                ndc,
                ndc_description,
                nadac_per_unit as current_price,
                prev_price,
                effective_date as current_date,
                prev_date as previous_date,
                pricing_unit,
                classification_for_rate_setting as drug_type,
                ROUND(((nadac_per_unit - prev_price) / prev_price * 100)::numeric, 2) as percent_change,
                nadac_per_unit - prev_price as absolute_change
            FROM ranked_prices
            WHERE prev_price IS NOT NULL AND prev_price > 0
            {change_filter}
            ORDER BY ABS(percent_change) DESC
            LIMIT :limit OFFSET :offset
        """

        date_filter = ""
        type_filter = ""
        change_filter = ""
        params = {"limit": limit, "offset": offset}

        if start_date:
            date_filter += " AND effective_date >= :start_date"
            params["start_date"] = start_date
        if end_date:
            date_filter += " AND effective_date <= :end_date"
            params["end_date"] = end_date
        if drug_type:
            type_filter = " AND classification_for_rate_setting = :drug_type"
            params["drug_type"] = drug_type

        change_conditions = []
        if min_change_percent is not None:
            change_conditions.append("percent_change >= :min_change")
            params["min_change"] = min_change_percent
        if max_change_percent is not None:
            change_conditions.append("percent_change <= :max_change")
            params["max_change"] = max_change_percent

        if change_conditions:
            change_filter = " AND " + " AND ".join(change_conditions)

        formatted_query = query.format(
            date_filter=date_filter,
            type_filter=type_filter,
            change_filter=change_filter
        )

        results = self.db.execute(text(formatted_query), params).fetchall()

        return [
            PriceChange(
                ndc=r.ndc,
                ndc_description=r.ndc_description,
                current_price=r.current_price,
                previous_price=r.prev_price,
                current_date=r.current_date,
                previous_date=r.previous_date,
                percent_change=r.percent_change,
                absolute_change=r.absolute_change,
                pricing_unit=r.pricing_unit,
                drug_type=r.drug_type
            )
            for r in results
        ], len(results)

    def get_top_inflation(
        self,
        top_n: int = 20,
        ascending: bool = False,
        drug_type: Optional[str] = None,
        min_days: int = 30
    ) -> List[TopInflationDrug]:
        """Get drugs with highest or lowest total inflation."""
        query = """
            WITH first_last AS (
                SELECT
                    ndc,
                    ndc_description,
                    classification_for_rate_setting,
                    FIRST_VALUE(nadac_per_unit) OVER w as first_price,
                    LAST_VALUE(nadac_per_unit) OVER w as latest_price,
                    FIRST_VALUE(effective_date) OVER w as first_date,
                    LAST_VALUE(effective_date) OVER w as latest_date
                FROM nadac_prices
                WHERE 1=1
                {type_filter}
                WINDOW w AS (
                    PARTITION BY ndc
                    ORDER BY effective_date
                    ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
                )
            ),
            distinct_drugs AS (
                SELECT DISTINCT ON (ndc)
                    ndc,
                    ndc_description,
                    classification_for_rate_setting as drug_type,
                    first_price,
                    latest_price,
                    first_date,
                    latest_date,
                    (latest_date - first_date) as period_days,
                    CASE WHEN first_price > 0
                        THEN ROUND(((latest_price - first_price) / first_price * 100)::numeric, 2)
                        ELSE 0
                    END as total_percent_change
                FROM first_last
                WHERE first_price > 0
                  AND (latest_date - first_date) >= :min_days
            )
            SELECT *
            FROM distinct_drugs
            ORDER BY total_percent_change {order}
            LIMIT :limit
        """

        type_filter = ""
        params = {"limit": top_n, "min_days": min_days}

        if drug_type:
            type_filter = " AND classification_for_rate_setting = :drug_type"
            params["drug_type"] = drug_type

        order = "ASC" if ascending else "DESC"
        formatted_query = query.format(type_filter=type_filter, order=order)

        results = self.db.execute(text(formatted_query), params).fetchall()

        return [
            TopInflationDrug(
                ndc=r.ndc,
                ndc_description=r.ndc_description,
                drug_type=r.drug_type,
                first_price=r.first_price,
                latest_price=r.latest_price,
                total_percent_change=r.total_percent_change,
                period_days=r.period_days
            )
            for r in results
        ]

    def get_inflation_stats(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        drug_type: Optional[str] = None
    ) -> InflationStats:
        """Get overall inflation statistics."""
        query = """
            WITH drug_changes AS (
                SELECT
                    ndc,
                    FIRST_VALUE(nadac_per_unit) OVER w as first_price,
                    LAST_VALUE(nadac_per_unit) OVER w as latest_price,
                    FIRST_VALUE(effective_date) OVER w as first_date,
                    LAST_VALUE(effective_date) OVER w as latest_date
                FROM nadac_prices
                WHERE 1=1
                {date_filter}
                {type_filter}
                WINDOW w AS (
                    PARTITION BY ndc
                    ORDER BY effective_date
                    ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
                )
            ),
            distinct_changes AS (
                SELECT DISTINCT ON (ndc)
                    ndc,
                    first_price,
                    latest_price,
                    first_date,
                    latest_date,
                    CASE WHEN first_price > 0
                        THEN ((latest_price - first_price) / first_price * 100)
                        ELSE 0
                    END as percent_change
                FROM drug_changes
                WHERE first_price > 0
            )
            SELECT
                COUNT(*) as total_drugs,
                SUM(CASE WHEN percent_change > 0.01 THEN 1 ELSE 0 END) as increases,
                SUM(CASE WHEN percent_change < -0.01 THEN 1 ELSE 0 END) as decreases,
                SUM(CASE WHEN percent_change BETWEEN -0.01 AND 0.01 THEN 1 ELSE 0 END) as unchanged,
                ROUND(AVG(percent_change)::numeric, 2) as avg_change,
                ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY percent_change)::numeric, 2) as median_change,
                MIN(first_date) as date_start,
                MAX(latest_date) as date_end
            FROM distinct_changes
        """

        date_filter = ""
        type_filter = ""
        params = {}

        if start_date:
            date_filter += " AND effective_date >= :start_date"
            params["start_date"] = start_date
        if end_date:
            date_filter += " AND effective_date <= :end_date"
            params["end_date"] = end_date
        if drug_type:
            type_filter = " AND classification_for_rate_setting = :drug_type"
            params["drug_type"] = drug_type

        formatted_query = query.format(date_filter=date_filter, type_filter=type_filter)

        result = self.db.execute(text(formatted_query), params).fetchone()

        return InflationStats(
            total_drugs_tracked=result.total_drugs or 0,
            drugs_with_increases=result.increases or 0,
            drugs_with_decreases=result.decreases or 0,
            drugs_unchanged=result.unchanged or 0,
            average_percent_change=Decimal(str(result.avg_change or 0)),
            median_percent_change=Decimal(str(result.median_change or 0)),
            date_range_start=result.date_start or date.today(),
            date_range_end=result.date_end or date.today()
        )

    def get_ingestion_status(self, limit: int = 10) -> List[IngestionLog]:
        """Get recent ingestion log entries."""
        return (
            self.db.query(IngestionLog)
            .order_by(desc(IngestionLog.started_at))
            .limit(limit)
            .all()
        )
