"""Application configuration."""
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    database_url: str = "postgresql://nadac_user:nadac_pass@localhost:5432/nadac"
    nadac_api_base_url: str = "https://data.medicaid.gov/api/1/datastore/query"

    # NADAC dataset UUIDs for different years (from data.medicaid.gov)
    nadac_dataset_2024: str = "99315a95-37ac-4eee-946a-3c523b4c481e"
    nadac_dataset_2023: str = "dfa2a059-e01f-4fa1-8d06-ef5e51fb63bf"
    nadac_dataset_2022: str = "39303f50-cd00-4be6-9b7a-e5d6c94a03cd"
    nadac_dataset_2021: str = "7030d26d-e770-4f5b-a389-9f0ce2ad5de6"

    # API settings
    api_page_size: int = 500
    max_pages_per_request: int = 100  # Safety limit

    class Config:
        env_file = ".env"
        extra = "allow"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
