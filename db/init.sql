-- NADAC Drug Price Inflation Tracker Database Schema

-- Main table for storing NADAC weekly price data
CREATE TABLE IF NOT EXISTS nadac_prices (
    id SERIAL PRIMARY KEY,
    ndc VARCHAR(11) NOT NULL,                    -- National Drug Code (11 digits)
    ndc_description TEXT NOT NULL,               -- Drug name/description
    nadac_per_unit DECIMAL(12, 6) NOT NULL,     -- Price per unit
    effective_date DATE NOT NULL,                -- Date this price became effective
    pricing_unit VARCHAR(10),                    -- EA, ML, GM, etc.
    pharmacy_type_indicator VARCHAR(5),          -- C/I (Community/Institutional)
    otc VARCHAR(1),                              -- Y/N (Over-the-counter)
    explanation_code VARCHAR(10),                -- Explanation for pricing
    classification_for_rate_setting VARCHAR(5),  -- G/B/N (Generic/Brand/N/A)
    corresponding_generic_drug_nadac DECIMAL(12, 6),
    corresponding_generic_drug_effective_date DATE,
    as_of_date DATE NOT NULL,                    -- Survey date
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Unique constraint to prevent duplicate entries
    CONSTRAINT unique_ndc_effective UNIQUE (ndc, effective_date, as_of_date)
);

-- Index for fast lookups
CREATE INDEX IF NOT EXISTS idx_nadac_ndc ON nadac_prices(ndc);
CREATE INDEX IF NOT EXISTS idx_nadac_effective_date ON nadac_prices(effective_date);
CREATE INDEX IF NOT EXISTS idx_nadac_description ON nadac_prices(ndc_description);
CREATE INDEX IF NOT EXISTS idx_nadac_as_of_date ON nadac_prices(as_of_date);

-- View for price changes over time (inflation tracking)
CREATE OR REPLACE VIEW price_changes AS
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
)
SELECT
    ndc,
    ndc_description,
    nadac_per_unit as current_price,
    prev_price,
    effective_date,
    prev_date,
    pricing_unit,
    classification_for_rate_setting,
    CASE
        WHEN prev_price IS NOT NULL AND prev_price > 0
        THEN ROUND(((nadac_per_unit - prev_price) / prev_price * 100)::numeric, 2)
        ELSE NULL
    END as percent_change,
    nadac_per_unit - COALESCE(prev_price, nadac_per_unit) as absolute_change
FROM ranked_prices
WHERE prev_price IS NOT NULL;

-- Table to track data ingestion runs
CREATE TABLE IF NOT EXISTS ingestion_log (
    id SERIAL PRIMARY KEY,
    started_at TIMESTAMP NOT NULL,
    completed_at TIMESTAMP,
    records_fetched INTEGER DEFAULT 0,
    records_inserted INTEGER DEFAULT 0,
    status VARCHAR(20) DEFAULT 'running',
    error_message TEXT,
    year INTEGER
);

-- Materialized view for inflation summary by drug
CREATE MATERIALIZED VIEW IF NOT EXISTS drug_inflation_summary AS
SELECT
    ndc,
    ndc_description,
    classification_for_rate_setting as drug_type,
    pricing_unit,
    MIN(effective_date) as first_price_date,
    MAX(effective_date) as latest_price_date,
    MIN(nadac_per_unit) as min_price,
    MAX(nadac_per_unit) as max_price,
    (SELECT nadac_per_unit FROM nadac_prices np2
     WHERE np2.ndc = nadac_prices.ndc
     ORDER BY effective_date ASC LIMIT 1) as first_price,
    (SELECT nadac_per_unit FROM nadac_prices np3
     WHERE np3.ndc = nadac_prices.ndc
     ORDER BY effective_date DESC LIMIT 1) as latest_price,
    COUNT(DISTINCT effective_date) as price_change_count
FROM nadac_prices
GROUP BY ndc, ndc_description, classification_for_rate_setting, pricing_unit;

CREATE UNIQUE INDEX IF NOT EXISTS idx_drug_inflation_ndc ON drug_inflation_summary(ndc);

-- Function to refresh the materialized view
CREATE OR REPLACE FUNCTION refresh_inflation_summary()
RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY drug_inflation_summary;
END;
$$ LANGUAGE plpgsql;
