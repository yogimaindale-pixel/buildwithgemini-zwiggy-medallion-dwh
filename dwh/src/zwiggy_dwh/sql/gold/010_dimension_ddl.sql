-- Gold Layer Dimension DDLs (SCD2 Structure)

-- 1. dim_customer
CREATE TABLE IF NOT EXISTS gold.dim_customer (
    customer_sk BIGSERIAL PRIMARY KEY,
    customer_id BIGINT NOT NULL,
    name VARCHAR(100),
    email_masked VARCHAR(64),
    phone_masked VARCHAR(64),
    valid_from TIMESTAMPTZ NOT NULL,
    valid_to TIMESTAMPTZ,
    dw_is_current BOOLEAN NOT NULL DEFAULT TRUE,
    dw_version INT NOT NULL DEFAULT 1,
    dw_batch_id BIGINT,
    dw_ingest_ts_utc TIMESTAMPTZ DEFAULT NOW()
);

-- Seed Unknown row (-1)
INSERT INTO gold.dim_customer (customer_sk, customer_id, name, valid_from, dw_is_current)
VALUES (-1, -1, 'UNKNOWN', '1900-01-01'::timestamptz, true)
ON CONFLICT (customer_sk) DO NOTHING;

-- 2. dim_address
CREATE TABLE IF NOT EXISTS gold.dim_address (
    address_sk BIGSERIAL PRIMARY KEY,
    address_id BIGINT NOT NULL,
    customer_id BIGINT,
    address_line TEXT,
    city VARCHAR(50),
    state VARCHAR(50),
    pincode VARCHAR(20),
    valid_from TIMESTAMPTZ NOT NULL,
    valid_to TIMESTAMPTZ,
    dw_is_current BOOLEAN NOT NULL DEFAULT TRUE,
    dw_version INT NOT NULL DEFAULT 1,
    dw_batch_id BIGINT,
    dw_ingest_ts_utc TIMESTAMPTZ DEFAULT NOW()
);

INSERT INTO gold.dim_address (address_sk, address_id, address_line, valid_from, dw_is_current)
VALUES (-1, -1, 'UNKNOWN', '1900-01-01'::timestamptz, true)
ON CONFLICT (address_sk) DO NOTHING;

-- 3. dim_restaurant
CREATE TABLE IF NOT EXISTS gold.dim_restaurant (
    restaurant_sk BIGSERIAL PRIMARY KEY,
    restaurant_id BIGINT NOT NULL,
    name VARCHAR(100),
    cuisine VARCHAR(50),
    city VARCHAR(50),
    is_active BOOLEAN,
    valid_from TIMESTAMPTZ NOT NULL,
    valid_to TIMESTAMPTZ,
    dw_is_current BOOLEAN NOT NULL DEFAULT TRUE,
    dw_version INT NOT NULL DEFAULT 1,
    dw_batch_id BIGINT,
    dw_ingest_ts_utc TIMESTAMPTZ DEFAULT NOW()
);

INSERT INTO gold.dim_restaurant (restaurant_sk, restaurant_id, name, valid_from, dw_is_current)
VALUES (-1, -1, 'UNKNOWN', '1900-01-01'::timestamptz, true)
ON CONFLICT (restaurant_sk) DO NOTHING;

-- 4. dim_menu_item
CREATE TABLE IF NOT EXISTS gold.dim_menu_item (
    menu_item_sk BIGSERIAL PRIMARY KEY,
    item_id BIGINT NOT NULL,
    restaurant_id BIGINT,
    category_id BIGINT,
    name VARCHAR(100),
    price NUMERIC(12,2),
    is_available BOOLEAN,
    valid_from TIMESTAMPTZ NOT NULL,
    valid_to TIMESTAMPTZ,
    dw_is_current BOOLEAN NOT NULL DEFAULT TRUE,
    dw_version INT NOT NULL DEFAULT 1,
    dw_batch_id BIGINT,
    dw_ingest_ts_utc TIMESTAMPTZ DEFAULT NOW()
);

INSERT INTO gold.dim_menu_item (menu_item_sk, item_id, name, valid_from, dw_is_current)
VALUES (-1, -1, 'UNKNOWN', '1900-01-01'::timestamptz, true)
ON CONFLICT (menu_item_sk) DO NOTHING;

-- 5. dim_delivery_partner
CREATE TABLE IF NOT EXISTS gold.dim_delivery_partner (
    partner_sk BIGSERIAL PRIMARY KEY,
    partner_id BIGINT NOT NULL,
    name VARCHAR(100),
    phone_masked VARCHAR(64),
    vehicle_type VARCHAR(50),
    is_active BOOLEAN,
    valid_from TIMESTAMPTZ NOT NULL,
    valid_to TIMESTAMPTZ,
    dw_is_current BOOLEAN NOT NULL DEFAULT TRUE,
    dw_version INT NOT NULL DEFAULT 1,
    dw_batch_id BIGINT,
    dw_ingest_ts_utc TIMESTAMPTZ DEFAULT NOW()
);

INSERT INTO gold.dim_delivery_partner (partner_sk, partner_id, name, valid_from, dw_is_current)
VALUES (-1, -1, 'UNKNOWN', '1900-01-01'::timestamptz, true)
ON CONFLICT (partner_sk) DO NOTHING;

-- 6. dim_restaurant_owner
CREATE TABLE IF NOT EXISTS gold.dim_restaurant_owner (
    owner_sk BIGSERIAL PRIMARY KEY,
    owner_id BIGINT NOT NULL,
    restaurant_id BIGINT,
    name VARCHAR(100),
    email_masked VARCHAR(64),
    phone_masked VARCHAR(64),
    valid_from TIMESTAMPTZ NOT NULL,
    valid_to TIMESTAMPTZ,
    dw_is_current BOOLEAN NOT NULL DEFAULT TRUE,
    dw_version INT NOT NULL DEFAULT 1,
    dw_batch_id BIGINT,
    dw_ingest_ts_utc TIMESTAMPTZ DEFAULT NOW()
);

INSERT INTO gold.dim_restaurant_owner (owner_sk, owner_id, name, valid_from, dw_is_current)
VALUES (-1, -1, 'UNKNOWN', '1900-01-01'::timestamptz, true)
ON CONFLICT (owner_sk) DO NOTHING;

-- 7. dim_code
CREATE TABLE IF NOT EXISTS gold.dim_code (
    code_sk BIGSERIAL PRIMARY KEY,
    code_type VARCHAR(50) NOT NULL,
    code_value VARCHAR(50) NOT NULL,
    description TEXT,
    dw_batch_id BIGINT
);

INSERT INTO gold.dim_code (code_sk, code_type, code_value, description)
VALUES (-1, 'UNKNOWN', 'UNKNOWN', 'UNKNOWN')
ON CONFLICT (code_sk) DO NOTHING;

-- 8. dim_order_flag
CREATE TABLE IF NOT EXISTS gold.dim_order_flag (
    flag_sk BIGSERIAL PRIMARY KEY,
    cohort_id VARCHAR(10),
    is_discounted BOOLEAN,
    has_review BOOLEAN
);

INSERT INTO gold.dim_order_flag (flag_sk, cohort_id, is_discounted, has_review)
VALUES (-1, 'UNKNOWN', false, false)
ON CONFLICT (flag_sk) DO NOTHING;

-- 9. dim_date
CREATE TABLE IF NOT EXISTS gold.dim_date (
    date_sk INT PRIMARY KEY, -- YYYYMMDD
    full_date DATE NOT NULL,
    year INT NOT NULL,
    quarter INT NOT NULL,
    month INT NOT NULL,
    day_of_month INT NOT NULL,
    day_of_week INT NOT NULL,
    is_weekend BOOLEAN NOT NULL
);

INSERT INTO gold.dim_date (date_sk, full_date, year, quarter, month, day_of_month, day_of_week, is_weekend)
VALUES (-1, '1900-01-01', 1900, 1, 1, 1, 1, false)
ON CONFLICT (date_sk) DO NOTHING;

-- 10. dim_time
CREATE TABLE IF NOT EXISTS gold.dim_time (
    time_sk INT PRIMARY KEY, -- HH24MI
    hour INT NOT NULL,
    minute INT NOT NULL
);

INSERT INTO gold.dim_time (time_sk, hour, minute)
VALUES (-1, 0, 0)
ON CONFLICT (time_sk) DO NOTHING;
