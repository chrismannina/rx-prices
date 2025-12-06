"""Client for fetching NADAC data from CMS data.medicaid.gov API."""
import httpx
from typing import AsyncIterator, Optional, Dict, Any, List
from datetime import datetime
import logging

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class NADACClient:
    """Client for the CMS NADAC API (data.medicaid.gov DKAN API)."""

    # Mapping of years to dataset UUIDs
    DATASET_IDS = {
        2024: "99315a95-37ac-4eee-946a-3c523b4c481e",
        2023: "dfa2a059-e01f-4fa1-8d06-ef5e51fb63bf",
        2022: "39303f50-cd00-4be6-9b7a-e5d6c94a03cd",
        2021: "7030d26d-e770-4f5b-a389-9f0ce2ad5de6",
        2020: "be0e26a6-2b98-4d11-9b73-2ee5a83d5d05",
        2019: "cc87bf38-8a57-426c-8a58-0f79e8ade1a4",
    }

    # Column name mapping from API to our database
    COLUMN_MAPPING = {
        "ndc": "ndc",
        "ndc_description": "ndc_description",
        "nadac_per_unit": "nadac_per_unit",
        "effective_date": "effective_date",
        "pricing_unit": "pricing_unit",
        "pharmacy_type_indicator": "pharmacy_type_indicator",
        "otc": "otc",
        "explanation_code": "explanation_code",
        "classification_for_rate_setting": "classification_for_rate_setting",
        "corresponding_generic_drug_nadac_per_unit": "corresponding_generic_drug_nadac",
        "corresponding_generic_drug_effective_date": "corresponding_generic_drug_effective_date",
        "as_of_date": "as_of_date",
    }

    def __init__(self, timeout: float = 30.0):
        """Initialize the NADAC client."""
        self.base_url = settings.nadac_api_base_url
        self.timeout = timeout
        self.page_size = settings.api_page_size

    def get_dataset_id(self, year: int) -> Optional[str]:
        """Get the dataset UUID for a given year."""
        return self.DATASET_IDS.get(year)

    async def fetch_page(
        self,
        year: int,
        offset: int = 0,
        limit: int = 500,
        client: Optional[httpx.AsyncClient] = None
    ) -> Dict[str, Any]:
        """Fetch a single page of NADAC data."""
        dataset_id = self.get_dataset_id(year)
        if not dataset_id:
            raise ValueError(f"No dataset available for year {year}")

        url = f"{self.base_url}/{dataset_id}/0"
        params = {
            "offset": offset,
            "limit": limit,
        }

        should_close = client is None
        if client is None:
            client = httpx.AsyncClient(timeout=self.timeout)

        try:
            response = await client.get(url, params=params)
            response.raise_for_status()
            return response.json()
        finally:
            if should_close:
                await client.aclose()

    async def fetch_all(
        self,
        year: int,
        max_records: Optional[int] = None
    ) -> AsyncIterator[List[Dict[str, Any]]]:
        """Fetch all NADAC data for a given year, yielding batches."""
        offset = 0
        total_fetched = 0

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            while True:
                logger.info(f"Fetching page at offset {offset} for year {year}")

                try:
                    result = await self.fetch_page(year, offset, self.page_size, client)
                except httpx.HTTPError as e:
                    logger.error(f"HTTP error fetching NADAC data: {e}")
                    raise

                records = result.get("results", [])
                if not records:
                    logger.info(f"No more records at offset {offset}")
                    break

                # Transform column names
                transformed_records = []
                for record in records:
                    transformed = {}
                    for api_col, db_col in self.COLUMN_MAPPING.items():
                        if api_col in record:
                            transformed[db_col] = record[api_col]
                    transformed_records.append(transformed)

                yield transformed_records

                total_fetched += len(records)
                logger.info(f"Fetched {total_fetched} records so far")

                if max_records and total_fetched >= max_records:
                    logger.info(f"Reached max records limit: {max_records}")
                    break

                if len(records) < self.page_size:
                    logger.info("Last page reached (partial page)")
                    break

                offset += self.page_size

    def transform_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """Transform a raw API record to our database format."""
        transformed = {}

        for api_col, db_col in self.COLUMN_MAPPING.items():
            value = record.get(api_col)
            if value is not None:
                # Handle date fields
                if "date" in db_col and value:
                    try:
                        # Try parsing different date formats
                        for fmt in ["%Y-%m-%d", "%m/%d/%Y", "%Y-%m-%dT%H:%M:%S"]:
                            try:
                                value = datetime.strptime(value, fmt).date()
                                break
                            except ValueError:
                                continue
                    except Exception:
                        value = None

                # Handle numeric fields
                elif db_col in ["nadac_per_unit", "corresponding_generic_drug_nadac"]:
                    try:
                        value = float(value) if value else None
                    except (ValueError, TypeError):
                        value = None

                transformed[db_col] = value

        return transformed
