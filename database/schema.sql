 -- =========================================================
-- 1. COMPANY PROFILE
-- One row per company/ticker
-- =========================================================

CREATE TABLE IF NOT EXISTS companies (
    company_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    ticker VARCHAR(20) NOT NULL UNIQUE,
    company_name TEXT NOT NULL,

    cik VARCHAR(20),
    isin VARCHAR(20),
    cusip VARCHAR(20),

    exchange VARCHAR(100),
    exchange_full_name TEXT,
    currency VARCHAR(10),

    sector TEXT,
    industry TEXT,
    website TEXT,
    description TEXT,
    ceo TEXT,
    country VARCHAR(100),

    market_cap NUMERIC(24, 2),
    current_price NUMERIC(20, 6),
    beta NUMERIC(12, 6),
    last_dividend NUMERIC(20, 6),
    ipo_date DATE,
    is_actively_trading BOOLEAN,

    -- Complete FMP profile response, including future fields .The original API response or additional fields  haven't modeled separately.JSONB store the raw json struture 
    raw_payload JSONB NOT NULL DEFAULT '{}'::jsonb,  

    fetched_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


-- =========================================================
-- 2. INCOME STATEMENT
-- One row per company, reporting date and period
-- =========================================================

CREATE TABLE IF NOT EXISTS income_statements (
    income_statement_id BIGINT
        GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    company_id BIGINT NOT NULL
        REFERENCES companies(company_id) ON DELETE CASCADE,

    report_date DATE NOT NULL,
    fiscal_year INTEGER,
    period VARCHAR(10) NOT NULL,  -- FY, Q1, Q2, Q3, Q4
    reported_currency VARCHAR(10),

    filing_date DATE,
    accepted_date TIMESTAMP,

    revenue NUMERIC(24, 2),
    cost_of_revenue NUMERIC(24, 2),
    gross_profit NUMERIC(24, 2),
    operating_expenses NUMERIC(24, 2),
    operating_income NUMERIC(24, 2),
    ebit NUMERIC(24, 2),
    ebitda NUMERIC(24, 2),
    income_before_tax NUMERIC(24, 2),
    income_tax_expense NUMERIC(24, 2),
    net_income NUMERIC(24, 2),
    eps NUMERIC(20, 6),
    eps_diluted NUMERIC(20, 6),

    raw_payload JSONB NOT NULL DEFAULT '{}'::jsonb,

    fetched_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_income_statement_period
        UNIQUE (company_id, report_date, period)
);


-- =========================================================
-- 3. BALANCE SHEET
-- One row per company, reporting date and period
-- =========================================================

CREATE TABLE IF NOT EXISTS balance_sheets (
    balance_sheet_id BIGINT
        GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    company_id BIGINT NOT NULL
        REFERENCES companies(company_id) ON DELETE CASCADE,

    report_date DATE NOT NULL,
    fiscal_year INTEGER,
    period VARCHAR(10) NOT NULL,
    reported_currency VARCHAR(10),

    filing_date DATE,
    accepted_date TIMESTAMP,

    cash_and_cash_equivalents NUMERIC(24, 2),
    total_current_assets NUMERIC(24, 2),
    total_assets NUMERIC(24, 2),
    total_current_liabilities NUMERIC(24, 2),
    total_liabilities NUMERIC(24, 2),
    total_stockholders_equity NUMERIC(24, 2),
    total_equity NUMERIC(24, 2),
    total_debt NUMERIC(24, 2),
    net_debt NUMERIC(24, 2),

    raw_payload JSONB NOT NULL DEFAULT '{}'::jsonb,

    fetched_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_balance_sheet_period
        UNIQUE (company_id, report_date, period)
);


-- =========================================================
-- 4. CASH FLOW STATEMENT
-- Implement its API loader after the first three workflows
-- =========================================================

CREATE TABLE IF NOT EXISTS cash_flow_statements (
    cash_flow_statement_id BIGINT
        GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    company_id BIGINT NOT NULL
        REFERENCES companies(company_id) ON DELETE CASCADE,

    report_date DATE NOT NULL,
    fiscal_year INTEGER,
    period VARCHAR(10) NOT NULL,
    reported_currency VARCHAR(10),

    filing_date DATE,
    accepted_date TIMESTAMP,

    net_income NUMERIC(24, 2),
    operating_cash_flow NUMERIC(24, 2),
    investing_cash_flow NUMERIC(24, 2),
    financing_cash_flow NUMERIC(24, 2),
    capital_expenditure NUMERIC(24, 2),
    free_cash_flow NUMERIC(24, 2),
    net_change_in_cash NUMERIC(24, 2),

    raw_payload JSONB NOT NULL DEFAULT '{}'::jsonb,

    fetched_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_cash_flow_period
        UNIQUE (company_id, report_date, period)
);



-- =========================================================
-- 5. Historical Stock Price and Volume
-- =========================================================
-- For now skip it 

-- CREATE TABLE IF NOT EXISTS historical_stock_prices (
--     historical_stock_price_id BIGINT
--         GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

--     company_id BIGINT NOT NULL
--         REFERENCES companies(company_id) ON DELETE CASCADE,

--     date DATE NOT NULL,
--     open NUMERIC(20, 6),
--     high NUMERIC(20, 6),
--     low NUMERIC(20, 6),
--     close NUMERIC(20, 6),
--     change_percent NUMERIC(12, 6),
--     volume BIGINT,

--     raw_payload JSONB NOT NULL DEFAULT '{}'::jsonb,

--     fetched_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

--     CONSTRAINT uq_historical_stock_price_date
--         UNIQUE (company_id, date)
-- );





-- =========================================================
-- 6. INDEXES
-- Help common lookups and time-period queries
-- =========================================================

CREATE INDEX IF NOT EXISTS idx_income_company_year
    ON income_statements(company_id, fiscal_year);

CREATE INDEX IF NOT EXISTS idx_balance_company_year
    ON balance_sheets(company_id, fiscal_year);

CREATE INDEX IF NOT EXISTS idx_cashflow_company_year
    ON cash_flow_statements(company_id, fiscal_year);

CREATE INDEX IF NOT EXISTS idx_income_report_date
    ON income_statements(report_date);