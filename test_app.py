#!/usr/bin/env python3
"""Test script for NADAC Drug Price Inflation Tracker."""
import sys
import os
from datetime import date, timedelta
from decimal import Decimal

# Add app directory to path
sys.path.insert(0, '/home/user/rx-prices')

# Override settings before importing app modules
os.environ['DATABASE_URL'] = 'sqlite:///test_nadac.db'

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from app.models import Base, NadacPrice, IngestionLog
from app.services import DrugPriceService

print("=" * 60)
print("NADAC Drug Price Inflation Tracker - Test Suite")
print("=" * 60)

# Setup test database
engine = create_engine('sqlite:///test_nadac.db', echo=False)
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)

def test_database_setup():
    """Test database tables are created correctly."""
    print("\n[TEST] Database Setup")
    db = Session()
    try:
        # Check tables exist
        result = db.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
        tables = [row[0] for row in result]

        assert 'nadac_prices' in tables, "nadac_prices table not found"
        assert 'ingestion_log' in tables, "ingestion_log table not found"
        print("  ✓ Tables created: nadac_prices, ingestion_log")
        return True
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        return False
    finally:
        db.close()

def test_insert_sample_data():
    """Insert sample drug pricing data."""
    print("\n[TEST] Insert Sample Data")
    db = Session()
    try:
        # Clear existing data
        db.query(NadacPrice).delete()
        db.commit()

        # Sample drugs with price history
        sample_data = [
            # Metformin - price increase
            {"ndc": "00093010101", "ndc_description": "METFORMIN HCL 500 MG TABLET",
             "nadac_per_unit": Decimal("0.02"), "effective_date": date(2023, 1, 1),
             "pricing_unit": "EA", "classification_for_rate_setting": "G", "as_of_date": date(2023, 1, 1)},
            {"ndc": "00093010101", "ndc_description": "METFORMIN HCL 500 MG TABLET",
             "nadac_per_unit": Decimal("0.025"), "effective_date": date(2023, 6, 1),
             "pricing_unit": "EA", "classification_for_rate_setting": "G", "as_of_date": date(2023, 6, 1)},
            {"ndc": "00093010101", "ndc_description": "METFORMIN HCL 500 MG TABLET",
             "nadac_per_unit": Decimal("0.03"), "effective_date": date(2024, 1, 1),
             "pricing_unit": "EA", "classification_for_rate_setting": "G", "as_of_date": date(2024, 1, 1)},

            # Lisinopril - price decrease
            {"ndc": "00093720110", "ndc_description": "LISINOPRIL 10 MG TABLET",
             "nadac_per_unit": Decimal("0.05"), "effective_date": date(2023, 1, 1),
             "pricing_unit": "EA", "classification_for_rate_setting": "G", "as_of_date": date(2023, 1, 1)},
            {"ndc": "00093720110", "ndc_description": "LISINOPRIL 10 MG TABLET",
             "nadac_per_unit": Decimal("0.04"), "effective_date": date(2023, 6, 1),
             "pricing_unit": "EA", "classification_for_rate_setting": "G", "as_of_date": date(2023, 6, 1)},
            {"ndc": "00093720110", "ndc_description": "LISINOPRIL 10 MG TABLET",
             "nadac_per_unit": Decimal("0.035"), "effective_date": date(2024, 1, 1),
             "pricing_unit": "EA", "classification_for_rate_setting": "G", "as_of_date": date(2024, 1, 1)},

            # Atorvastatin - stable
            {"ndc": "00591377110", "ndc_description": "ATORVASTATIN CALCIUM 10 MG TABLET",
             "nadac_per_unit": Decimal("0.10"), "effective_date": date(2023, 1, 1),
             "pricing_unit": "EA", "classification_for_rate_setting": "G", "as_of_date": date(2023, 1, 1)},
            {"ndc": "00591377110", "ndc_description": "ATORVASTATIN CALCIUM 10 MG TABLET",
             "nadac_per_unit": Decimal("0.10"), "effective_date": date(2024, 1, 1),
             "pricing_unit": "EA", "classification_for_rate_setting": "G", "as_of_date": date(2024, 1, 1)},

            # Brand drug example - large increase
            {"ndc": "00002323001", "ndc_description": "HUMALOG 100 UNIT/ML INJECTION",
             "nadac_per_unit": Decimal("25.50"), "effective_date": date(2023, 1, 1),
             "pricing_unit": "ML", "classification_for_rate_setting": "B", "as_of_date": date(2023, 1, 1)},
            {"ndc": "00002323001", "ndc_description": "HUMALOG 100 UNIT/ML INJECTION",
             "nadac_per_unit": Decimal("32.00"), "effective_date": date(2024, 1, 1),
             "pricing_unit": "ML", "classification_for_rate_setting": "B", "as_of_date": date(2024, 1, 1)},
        ]

        for data in sample_data:
            price = NadacPrice(**data)
            db.add(price)

        db.commit()

        count = db.query(NadacPrice).count()
        print(f"  ✓ Inserted {count} sample price records")
        print(f"  ✓ Drugs: Metformin, Lisinopril, Atorvastatin, Humalog")
        return True
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        db.rollback()
        return False
    finally:
        db.close()

def test_drug_search():
    """Test drug search functionality."""
    print("\n[TEST] Drug Search")
    db = Session()
    try:
        service = DrugPriceService(db)

        # Search by name
        results, total = service.search_drugs("metformin", limit=10)
        assert len(results) > 0, "Should find Metformin"
        assert results[0].ndc == "00093010101"
        print(f"  ✓ Search 'metformin': Found {total} result(s)")

        # Search by partial name
        results, total = service.search_drugs("lisin", limit=10)
        assert len(results) > 0, "Should find Lisinopril"
        print(f"  ✓ Search 'lisin': Found {total} result(s)")

        # Search by NDC
        results, total = service.search_drugs("00591377110", limit=10)
        assert len(results) > 0, "Should find drug by NDC"
        print(f"  ✓ Search by NDC: Found {total} result(s)")

        return True
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()

def test_price_history():
    """Test price history retrieval."""
    print("\n[TEST] Price History")
    db = Session()
    try:
        service = DrugPriceService(db)

        history = service.get_price_history("00093010101")
        assert len(history) == 3, f"Metformin should have 3 price points, got {len(history)}"

        # Should be in chronological order
        assert history[0].effective_date < history[1].effective_date < history[2].effective_date
        print(f"  ✓ Metformin price history: {len(history)} records")
        print(f"    - {history[0].effective_date}: ${history[0].nadac_per_unit}")
        print(f"    - {history[-1].effective_date}: ${history[-1].nadac_per_unit}")

        return True
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        return False
    finally:
        db.close()

def test_inflation_calculation():
    """Test inflation calculation for individual drugs."""
    print("\n[TEST] Inflation Calculation")
    db = Session()
    try:
        service = DrugPriceService(db)

        # Metformin - should show 50% increase (0.02 -> 0.03)
        inflation = service.get_drug_inflation("00093010101")
        assert inflation is not None, "Should find inflation data"

        expected_change = 50.0  # (0.03 - 0.02) / 0.02 * 100
        actual_change = float(inflation.total_percent_change)
        assert abs(actual_change - expected_change) < 0.1, f"Expected ~{expected_change}%, got {actual_change}%"
        print(f"  ✓ Metformin inflation: {actual_change}% (expected {expected_change}%)")

        # Lisinopril - should show -30% decrease (0.05 -> 0.035)
        inflation = service.get_drug_inflation("00093720110")
        expected_change = -30.0  # (0.035 - 0.05) / 0.05 * 100
        actual_change = float(inflation.total_percent_change)
        assert abs(actual_change - expected_change) < 0.1, f"Expected ~{expected_change}%, got {actual_change}%"
        print(f"  ✓ Lisinopril inflation: {actual_change}% (expected {expected_change}%)")

        # Humalog (brand) - should show ~25.5% increase
        inflation = service.get_drug_inflation("00002323001")
        expected_change = 25.49  # (32 - 25.5) / 25.5 * 100
        actual_change = float(inflation.total_percent_change)
        assert abs(actual_change - expected_change) < 0.1, f"Expected ~{expected_change}%, got {actual_change}%"
        print(f"  ✓ Humalog inflation: {actual_change}% (expected ~{expected_change}%)")

        return True
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()

def test_api_endpoints():
    """Test FastAPI endpoints."""
    print("\n[TEST] API Endpoints")
    try:
        from fastapi.testclient import TestClient

        # Patch the database URL before importing main
        os.environ['DATABASE_URL'] = 'sqlite:///test_nadac.db'

        # Need to reimport to pick up the new DATABASE_URL
        from app.database import engine, SessionLocal
        from app.main import app

        # Override the dependency
        def override_get_db():
            db = Session()
            try:
                yield db
            finally:
                db.close()

        from app.database import get_db
        app.dependency_overrides[get_db] = override_get_db

        client = TestClient(app)

        # Test health endpoint
        response = client.get("/api/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"
        print("  ✓ GET /api/health: 200 OK")

        # Test drug search
        response = client.get("/api/drugs/search?q=metformin")
        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        print(f"  ✓ GET /api/drugs/search: Found {len(data['results'])} drug(s)")

        # Test price history
        response = client.get("/api/drugs/00093010101/history")
        assert response.status_code == 200
        data = response.json()
        assert len(data) > 0
        print(f"  ✓ GET /api/drugs/{{ndc}}/history: {len(data)} price points")

        # Test drug inflation
        response = client.get("/api/drugs/00093010101/inflation")
        assert response.status_code == 200
        data = response.json()
        assert "total_percent_change" in data
        print(f"  ✓ GET /api/drugs/{{ndc}}/inflation: {data['total_percent_change']}% change")

        # Test 404 for unknown drug
        response = client.get("/api/drugs/99999999999/history")
        assert response.status_code == 404
        print("  ✓ GET /api/drugs/{{unknown}}/history: 404 Not Found")

        return True
    except ImportError as e:
        print(f"  ⚠ Skipped (missing test dependencies): {e}")
        return True  # Not a failure, just missing optional dep
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_schema_validation():
    """Test Pydantic schemas."""
    print("\n[TEST] Schema Validation")
    try:
        from app.schemas import (
            DrugPriceResponse, DrugInflationSummary, PriceChange,
            SearchResult, InflationStats
        )
        from datetime import datetime

        # Test SearchResult
        result = SearchResult(
            ndc="00093010101",
            ndc_description="METFORMIN HCL 500 MG TABLET",
            latest_price=Decimal("0.03"),
            latest_date=date(2024, 1, 1),
            drug_type="G"
        )
        assert result.ndc == "00093010101"
        print("  ✓ SearchResult schema validates correctly")

        # Test DrugInflationSummary
        summary = DrugInflationSummary(
            ndc="00093010101",
            ndc_description="METFORMIN HCL 500 MG TABLET",
            drug_type="G",
            pricing_unit="EA",
            first_price_date=date(2023, 1, 1),
            latest_price_date=date(2024, 1, 1),
            first_price=Decimal("0.02"),
            latest_price=Decimal("0.03"),
            min_price=Decimal("0.02"),
            max_price=Decimal("0.03"),
            total_percent_change=Decimal("50.0"),
            price_change_count=3
        )
        assert summary.total_percent_change == Decimal("50.0")
        print("  ✓ DrugInflationSummary schema validates correctly")

        return True
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        return False

def cleanup():
    """Clean up test database."""
    import os
    if os.path.exists('test_nadac.db'):
        os.remove('test_nadac.db')
        print("\n  Cleaned up test database")

def main():
    """Run all tests."""
    results = []

    results.append(("Database Setup", test_database_setup()))
    results.append(("Insert Sample Data", test_insert_sample_data()))
    results.append(("Drug Search", test_drug_search()))
    results.append(("Price History", test_price_history()))
    results.append(("Inflation Calculation", test_inflation_calculation()))
    results.append(("Schema Validation", test_schema_validation()))
    results.append(("API Endpoints", test_api_endpoints()))

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    passed = sum(1 for _, r in results if r)
    failed = sum(1 for _, r in results if not r)

    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"  {status}: {name}")

    print(f"\nTotal: {passed} passed, {failed} failed")

    cleanup()

    return failed == 0

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
