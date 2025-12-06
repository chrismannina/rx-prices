"""Data ingestion service for NADAC data."""
import asyncio
import logging
from datetime import datetime, date
from typing import Optional, List, Dict, Any
from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert

from app.database import SessionLocal
from app.models import NadacPrice, IngestionLog
from app.nadac_client import NADACClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def parse_date(value: str) -> Optional[date]:
    """Parse date string to date object."""
    if not value:
        return None
    for fmt in ["%Y-%m-%d", "%m/%d/%Y", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f"]:
        try:
            return datetime.strptime(value.split("T")[0] if "T" in value else value, fmt.split("T")[0]).date()
        except ValueError:
            continue
    return None


def parse_decimal(value: Any) -> Optional[Decimal]:
    """Parse numeric value to Decimal."""
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except Exception:
        return None


def transform_record(record: Dict[str, Any]) -> Dict[str, Any]:
    """Transform API record to database format."""
    return {
        "ndc": str(record.get("ndc", "")).replace("-", "").strip(),
        "ndc_description": record.get("ndc_description", ""),
        "nadac_per_unit": parse_decimal(record.get("nadac_per_unit")),
        "effective_date": parse_date(record.get("effective_date")),
        "pricing_unit": record.get("pricing_unit"),
        "pharmacy_type_indicator": record.get("pharmacy_type_indicator"),
        "otc": record.get("otc"),
        "explanation_code": record.get("explanation_code"),
        "classification_for_rate_setting": record.get("classification_for_rate_setting"),
        "corresponding_generic_drug_nadac": parse_decimal(
            record.get("corresponding_generic_drug_nadac")
        ),
        "corresponding_generic_drug_effective_date": parse_date(
            record.get("corresponding_generic_drug_effective_date")
        ),
        "as_of_date": parse_date(record.get("as_of_date")),
    }


async def ingest_year(year: int, max_records: Optional[int] = None) -> Dict[str, int]:
    """Ingest NADAC data for a specific year."""
    client = NADACClient()
    db = SessionLocal()

    # Create ingestion log entry
    log = IngestionLog(
        started_at=datetime.utcnow(),
        status="running",
        year=year
    )
    db.add(log)
    db.commit()
    db.refresh(log)

    total_fetched = 0
    total_inserted = 0

    try:
        async for batch in client.fetch_all(year, max_records):
            # Transform records
            records = []
            for record in batch:
                transformed = transform_record(record)
                # Skip records with missing required fields
                if (
                    transformed["ndc"]
                    and transformed["ndc_description"]
                    and transformed["nadac_per_unit"] is not None
                    and transformed["effective_date"]
                    and transformed["as_of_date"]
                ):
                    records.append(transformed)

            if records:
                # Use upsert to handle duplicates
                stmt = insert(NadacPrice).values(records)
                stmt = stmt.on_conflict_do_nothing(
                    index_elements=["ndc", "effective_date", "as_of_date"]
                )
                result = db.execute(stmt)
                db.commit()

                inserted = result.rowcount if hasattr(result, "rowcount") else len(records)
                total_inserted += inserted

            total_fetched += len(batch)
            logger.info(f"Year {year}: Fetched {total_fetched}, Inserted {total_inserted}")

            # Update log periodically
            log.records_fetched = total_fetched
            log.records_inserted = total_inserted
            db.commit()

        # Success
        log.status = "completed"
        log.completed_at = datetime.utcnow()
        log.records_fetched = total_fetched
        log.records_inserted = total_inserted
        db.commit()

        # Refresh materialized view
        try:
            db.execute(text("SELECT refresh_inflation_summary()"))
            db.commit()
            logger.info("Refreshed inflation summary materialized view")
        except Exception as e:
            logger.warning(f"Could not refresh materialized view: {e}")

        logger.info(f"Completed ingestion for {year}: {total_fetched} fetched, {total_inserted} inserted")

    except Exception as e:
        logger.error(f"Ingestion failed for {year}: {e}")
        log.status = "failed"
        log.error_message = str(e)
        log.completed_at = datetime.utcnow()
        db.commit()
        raise

    finally:
        db.close()

    return {"fetched": total_fetched, "inserted": total_inserted}


async def ingest_all_years(years: Optional[List[int]] = None, max_records_per_year: Optional[int] = None):
    """Ingest NADAC data for multiple years."""
    if years is None:
        years = [2024, 2023, 2022, 2021]

    results = {}
    for year in years:
        logger.info(f"Starting ingestion for year {year}")
        try:
            result = await ingest_year(year, max_records_per_year)
            results[year] = result
        except Exception as e:
            logger.error(f"Failed to ingest year {year}: {e}")
            results[year] = {"error": str(e)}

    return results


def main():
    """Main entry point for CLI ingestion."""
    import argparse

    parser = argparse.ArgumentParser(description="Ingest NADAC data from CMS")
    parser.add_argument(
        "--years",
        type=int,
        nargs="+",
        default=[2024],
        help="Years to ingest (default: 2024)"
    )
    parser.add_argument(
        "--max-records",
        type=int,
        default=None,
        help="Maximum records per year (for testing)"
    )
    args = parser.parse_args()

    logger.info(f"Starting ingestion for years: {args.years}")
    results = asyncio.run(ingest_all_years(args.years, args.max_records))

    for year, result in results.items():
        logger.info(f"Year {year}: {result}")


if __name__ == "__main__":
    main()
