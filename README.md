# NADAC Drug Price Inflation Tracker

Track prescription drug price inflation using CMS NADAC (National Average Drug Acquisition Cost) data.

## Overview

This application fetches weekly drug pricing data from CMS (Centers for Medicare & Medicaid Services), stores it in PostgreSQL, and provides APIs and a dashboard to track price changes over time.

**Data Source:** [data.medicaid.gov NADAC Dataset](https://data.medicaid.gov/dataset/99315a95-37ac-4eee-946a-3c523b4c481e)

## Features

- **Data Ingestion**: Automated fetching of NADAC data from CMS API (2019-2024)
- **Price Tracking**: Historical price data storage and querying
- **Inflation Analysis**: Calculate price changes, percent increases, and annualized rates
- **REST API**: Full-featured API for integration with other systems
- **Web Dashboard**: Interactive UI for searching drugs and viewing price trends
- **Docker Setup**: Easy deployment with Docker Compose

## Quick Start

### Prerequisites

- Docker and Docker Compose
- (Optional) Python 3.11+ for local development

### Running with Docker

```bash
# Start the database and API
docker-compose up -d

# View logs
docker-compose logs -f api

# Run data ingestion for 2024
docker-compose run --rm ingestion python -m app.ingest --years 2024

# Or ingest multiple years
docker-compose run --rm ingestion python -m app.ingest --years 2024 2023 2022
```

The application will be available at:
- **Dashboard**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/api/health

### Local Development

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set environment variables
export DATABASE_URL="postgresql://nadac_user:nadac_pass@localhost:5432/nadac"

# Start PostgreSQL (if not using Docker)
docker-compose up -d db

# Run the API
uvicorn app.main:app --reload

# Run data ingestion
python -m app.ingest --years 2024
```

## API Endpoints

### Drug Search & Lookup

| Endpoint | Description |
|----------|-------------|
| `GET /api/drugs/search?q=metformin` | Search drugs by name or NDC |
| `GET /api/drugs/{ndc}/history` | Get price history for a drug |
| `GET /api/drugs/{ndc}/inflation` | Get inflation summary for a drug |

### Price Analysis

| Endpoint | Description |
|----------|-------------|
| `GET /api/price-changes` | Get price changes with filters |
| `GET /api/inflation/top?direction=highest` | Get top drugs by inflation |
| `GET /api/inflation/stats` | Get overall inflation statistics |

### Data Management

| Endpoint | Description |
|----------|-------------|
| `POST /api/ingest/{year}` | Trigger data ingestion for a year |
| `GET /api/ingest/status` | Get ingestion job status |
| `GET /api/summary` | Get data summary |

### Example API Calls

```bash
# Search for a drug
curl "http://localhost:8000/api/drugs/search?q=atorvastatin"

# Get price history
curl "http://localhost:8000/api/drugs/00093505698/history"

# Get top 10 drugs with highest price increases
curl "http://localhost:8000/api/inflation/top?n=10&direction=highest"

# Get overall inflation statistics
curl "http://localhost:8000/api/inflation/stats"

# Trigger data ingestion for 2024
curl -X POST "http://localhost:8000/api/ingest/2024"
```

## Data Schema

### nadac_prices Table

| Column | Description |
|--------|-------------|
| `ndc` | National Drug Code (11 digits) |
| `ndc_description` | Drug name/description |
| `nadac_per_unit` | Price per unit |
| `effective_date` | Date this price became effective |
| `pricing_unit` | Unit of measure (EA, ML, GM) |
| `classification_for_rate_setting` | G (Generic), B (Brand), N (N/A) |
| `as_of_date` | Survey/publication date |

## Configuration

Environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql://nadac_user:nadac_pass@localhost:5432/nadac` | PostgreSQL connection URL |
| `NADAC_API_BASE_URL` | `https://data.medicaid.gov/api/1/datastore/query` | CMS API base URL |

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   CMS NADAC     │────▶│   Ingestion     │────▶│   PostgreSQL    │
│   API           │     │   Service       │     │   Database      │
└─────────────────┘     └─────────────────┘     └────────┬────────┘
                                                         │
                        ┌─────────────────┐              │
                        │   FastAPI       │◀─────────────┘
                        │   Backend       │
                        └────────┬────────┘
                                 │
              ┌──────────────────┼──────────────────┐
              │                  │                  │
    ┌─────────▼─────────┐ ┌─────▼─────┐ ┌─────────▼─────────┐
    │   Web Dashboard   │ │  REST API │ │   External Apps   │
    │   (Browser)       │ │  (/docs)  │ │                   │
    └───────────────────┘ └───────────┘ └───────────────────┘
```

## Data Ingestion Notes

- NADAC data is updated weekly by CMS
- Each year's data is ~500K+ records
- Initial ingestion may take 10-30 minutes per year
- The ingestion process is idempotent (safe to re-run)
- A materialized view is refreshed after ingestion for faster queries

## License

MIT

## References

- [CMS NADAC Program](https://www.medicaid.gov/medicaid/nadac)
- [NADAC Methodology (PDF)](https://www.medicaid.gov/medicaid-chip-program-information/by-topics/prescription-drugs/ful-nadac-downloads/nadacmethodology.pdf)
- [Data.Medicaid.gov API](https://data.medicaid.gov)
