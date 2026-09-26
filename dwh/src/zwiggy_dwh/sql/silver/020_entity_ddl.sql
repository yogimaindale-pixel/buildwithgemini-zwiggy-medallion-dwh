-- Silver Layer Entity & Quarantine Table DDLs

-- Enable pgcrypto extension for digest hashing if available
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- 1. slv_customer & quarantine
CREATE TABLE IF NOT EXISTS silver.slv_customer (
    customer_id BIGINT PRIMARY KEY,
    name VARCHAR(100),
    email_masked VARCHAR(64),
    phone_masked VARCHAR(64),
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ,
    dw_batch_id BIGINT,
    dw_ingest_ts_utc TIMESTAMPTZ DEFAULT NOW(),
    dw_is_deleted BOOLEAN DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS silver.slv_customer_quarantine (
    quarantine_id BIGSERIAL PRIMARY KEY,
    dw_batch_id BIGINT,
    dw_quarantine_reason TEXT,
    dw_raw_payload JSONB,
    dw_quarantined_ts_utc TIMESTAMPTZ DEFAULT NOW()
);

-- 2. slv_address & quarantine
CREATE TABLE IF NOT EXISTS silver.slv_address (
    address_id BIGINT PRIMARY KEY,
    customer_id BIGINT,
    address_line TEXT,
    city VARCHAR(50),
    state VARCHAR(50),
    pincode VARCHAR(20),
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ,
    dw_batch_id BIGINT,
    dw_ingest_ts_utc TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS silver.slv_address_quarantine (
    quarantine_id BIGSERIAL PRIMARY KEY,
    dw_batch_id BIGINT,
    dw_quarantine_reason TEXT,
    dw_raw_payload JSONB,
    dw_quarantined_ts_utc TIMESTAMPTZ DEFAULT NOW()
);

-- 3. slv_restaurant & quarantine
CREATE TABLE IF NOT EXISTS silver.slv_restaurant (
    restaurant_id BIGINT PRIMARY KEY,
    name VARCHAR(100),
    cuisine VARCHAR(50),
    city VARCHAR(50),
    is_active BOOLEAN,
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ,
    dw_batch_id BIGINT,
    dw_ingest_ts_utc TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS silver.slv_restaurant_quarantine (
    quarantine_id BIGSERIAL PRIMARY KEY,
    dw_batch_id BIGINT,
    dw_quarantine_reason TEXT,
    dw_raw_payload JSONB,
    dw_quarantined_ts_utc TIMESTAMPTZ DEFAULT NOW()
);

-- 4. slv_restaurant_owner & quarantine
CREATE TABLE IF NOT EXISTS silver.slv_restaurant_owner (
    owner_id BIGINT PRIMARY KEY,
    restaurant_id BIGINT,
    name VARCHAR(100),
    email_masked VARCHAR(64),
    phone_masked VARCHAR(64),
    dw_batch_id BIGINT,
    dw_ingest_ts_utc TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS silver.slv_restaurant_owner_quarantine (
    quarantine_id BIGSERIAL PRIMARY KEY,
    dw_batch_id BIGINT,
    dw_quarantine_reason TEXT,
    dw_raw_payload JSONB,
    dw_quarantined_ts_utc TIMESTAMPTZ DEFAULT NOW()
);

-- 5. slv_menu_category & quarantine
CREATE TABLE IF NOT EXISTS silver.slv_menu_category (
    category_id BIGINT PRIMARY KEY,
    restaurant_id BIGINT,
    name VARCHAR(100),
    dw_batch_id BIGINT,
    dw_ingest_ts_utc TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS silver.slv_menu_category_quarantine (
    quarantine_id BIGSERIAL PRIMARY KEY,
    dw_batch_id BIGINT,
    dw_quarantine_reason TEXT,
    dw_raw_payload JSONB,
    dw_quarantined_ts_utc TIMESTAMPTZ DEFAULT NOW()
);

-- 6. slv_menu_item & quarantine
CREATE TABLE IF NOT EXISTS silver.slv_menu_item (
    item_id BIGINT PRIMARY KEY,
    restaurant_id BIGINT,
    category_id BIGINT,
    name VARCHAR(100),
    price NUMERIC(12,2),
    is_available BOOLEAN,
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ,
    dw_batch_id BIGINT,
    dw_ingest_ts_utc TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS silver.slv_menu_item_quarantine (
    quarantine_id BIGSERIAL PRIMARY KEY,
    dw_batch_id BIGINT,
    dw_quarantine_reason TEXT,
    dw_raw_payload JSONB,
    dw_quarantined_ts_utc TIMESTAMPTZ DEFAULT NOW()
);

-- 7. slv_delivery_partner & quarantine
CREATE TABLE IF NOT EXISTS silver.slv_delivery_partner (
    partner_id BIGINT PRIMARY KEY,
    name VARCHAR(100),
    phone_masked VARCHAR(64),
    vehicle_type VARCHAR(50),
    is_active BOOLEAN,
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ,
    dw_batch_id BIGINT,
    dw_ingest_ts_utc TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS silver.slv_delivery_partner_quarantine (
    quarantine_id BIGSERIAL PRIMARY KEY,
    dw_batch_id BIGINT,
    dw_quarantine_reason TEXT,
    dw_raw_payload JSONB,
    dw_quarantined_ts_utc TIMESTAMPTZ DEFAULT NOW()
);

-- 8. slv_order & quarantine
CREATE TABLE IF NOT EXISTS silver.slv_order (
    order_id BIGINT PRIMARY KEY,
    customer_id BIGINT,
    restaurant_id BIGINT,
    order_status VARCHAR(50),
    total_amount NUMERIC(12,2),
    discount_amount NUMERIC(12,2),
    delivery_fee NUMERIC(12,2),
    cohort_id VARCHAR(10),
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ,
    dw_batch_id BIGINT,
    dw_ingest_ts_utc TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS silver.slv_order_quarantine (
    quarantine_id BIGSERIAL PRIMARY KEY,
    dw_batch_id BIGINT,
    dw_quarantine_reason TEXT,
    dw_raw_payload JSONB,
    dw_quarantined_ts_utc TIMESTAMPTZ DEFAULT NOW()
);

-- 9. slv_order_item & quarantine
CREATE TABLE IF NOT EXISTS silver.slv_order_item (
    order_item_id BIGINT PRIMARY KEY,
    order_id BIGINT,
    item_id BIGINT,
    quantity INT,
    unit_price NUMERIC(12,2),
    item_total NUMERIC(12,2),
    dw_batch_id BIGINT,
    dw_ingest_ts_utc TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS silver.slv_order_item_quarantine (
    quarantine_id BIGSERIAL PRIMARY KEY,
    dw_batch_id BIGINT,
    dw_quarantine_reason TEXT,
    dw_raw_payload JSONB,
    dw_quarantined_ts_utc TIMESTAMPTZ DEFAULT NOW()
);

-- 10. slv_payment_attempt & quarantine
CREATE TABLE IF NOT EXISTS silver.slv_payment_attempt (
    attempt_id BIGINT PRIMARY KEY,
    order_id BIGINT,
    payment_method_raw VARCHAR(50),
    conformed_method VARCHAR(50),
    status VARCHAR(50),
    amount NUMERIC(12,2),
    created_at TIMESTAMPTZ,
    dw_batch_id BIGINT,
    dw_ingest_ts_utc TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS silver.slv_payment_attempt_quarantine (
    quarantine_id BIGSERIAL PRIMARY KEY,
    dw_batch_id BIGINT,
    dw_quarantine_reason TEXT,
    dw_raw_payload JSONB,
    dw_quarantined_ts_utc TIMESTAMPTZ DEFAULT NOW()
);

-- 11. slv_payment & quarantine
CREATE TABLE IF NOT EXISTS silver.slv_payment (
    payment_id BIGINT PRIMARY KEY,
    order_id BIGINT,
    payment_method VARCHAR(50),
    status VARCHAR(50),
    amount NUMERIC(12,2),
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ,
    dw_batch_id BIGINT,
    dw_ingest_ts_utc TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS silver.slv_payment_quarantine (
    quarantine_id BIGSERIAL PRIMARY KEY,
    dw_batch_id BIGINT,
    dw_quarantine_reason TEXT,
    dw_raw_payload JSONB,
    dw_quarantined_ts_utc TIMESTAMPTZ DEFAULT NOW()
);

-- 12. slv_delivery & quarantine
CREATE TABLE IF NOT EXISTS silver.slv_delivery (
    delivery_id BIGINT PRIMARY KEY,
    order_id BIGINT,
    partner_id BIGINT,
    delivery_status VARCHAR(50),
    assigned_at TIMESTAMPTZ,
    picked_up_at TIMESTAMPTZ,
    delivered_at TIMESTAMPTZ,
    dw_batch_id BIGINT,
    dw_ingest_ts_utc TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS silver.slv_delivery_quarantine (
    quarantine_id BIGSERIAL PRIMARY KEY,
    dw_batch_id BIGINT,
    dw_quarantine_reason TEXT,
    dw_raw_payload JSONB,
    dw_quarantined_ts_utc TIMESTAMPTZ DEFAULT NOW()
);

-- 13. slv_delivery_status & quarantine
CREATE TABLE IF NOT EXISTS silver.slv_delivery_status (
    history_id BIGINT PRIMARY KEY,
    delivery_id BIGINT,
    status VARCHAR(50),
    changed_at TIMESTAMPTZ,
    dw_batch_id BIGINT,
    dw_ingest_ts_utc TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS silver.slv_delivery_status_quarantine (
    quarantine_id BIGSERIAL PRIMARY KEY,
    dw_batch_id BIGINT,
    dw_quarantine_reason TEXT,
    dw_raw_payload JSONB,
    dw_quarantined_ts_utc TIMESTAMPTZ DEFAULT NOW()
);

-- 14. slv_order_review & quarantine
CREATE TABLE IF NOT EXISTS silver.slv_order_review (
    review_id BIGINT PRIMARY KEY,
    order_id BIGINT,
    rating INT,
    review_text TEXT,
    created_at TIMESTAMPTZ,
    dw_batch_id BIGINT,
    dw_ingest_ts_utc TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS silver.slv_order_review_quarantine (
    quarantine_id BIGSERIAL PRIMARY KEY,
    dw_batch_id BIGINT,
    dw_quarantine_reason TEXT,
    dw_raw_payload JSONB,
    dw_quarantined_ts_utc TIMESTAMPTZ DEFAULT NOW()
);

-- 15. slv_restaurant_review & quarantine
CREATE TABLE IF NOT EXISTS silver.slv_restaurant_review (
    review_id BIGINT PRIMARY KEY,
    restaurant_id BIGINT,
    customer_id BIGINT,
    rating INT,
    review_text TEXT,
    created_at TIMESTAMPTZ,
    dw_batch_id BIGINT,
    dw_ingest_ts_utc TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS silver.slv_restaurant_review_quarantine (
    quarantine_id BIGSERIAL PRIMARY KEY,
    dw_batch_id BIGINT,
    dw_quarantine_reason TEXT,
    dw_raw_payload JSONB,
    dw_quarantined_ts_utc TIMESTAMPTZ DEFAULT NOW()
);

-- 16. slv_cart_item & quarantine
CREATE TABLE IF NOT EXISTS silver.slv_cart_item (
    cart_item_id BIGINT PRIMARY KEY,
    customer_id BIGINT,
    item_id BIGINT,
    quantity INT,
    created_at TIMESTAMPTZ,
    dw_batch_id BIGINT,
    dw_ingest_ts_utc TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS silver.slv_cart_item_quarantine (
    quarantine_id BIGSERIAL PRIMARY KEY,
    dw_batch_id BIGINT,
    dw_quarantine_reason TEXT,
    dw_raw_payload JSONB,
    dw_quarantined_ts_utc TIMESTAMPTZ DEFAULT NOW()
);

-- 17. slv_discount_code & quarantine
CREATE TABLE IF NOT EXISTS silver.slv_discount_code (
    code_id BIGINT PRIMARY KEY,
    code_name VARCHAR(50),
    discount_pct NUMERIC(5,2),
    is_active BOOLEAN,
    dw_batch_id BIGINT,
    dw_ingest_ts_utc TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS silver.slv_discount_code_quarantine (
    quarantine_id BIGSERIAL PRIMARY KEY,
    dw_batch_id BIGINT,
    dw_quarantine_reason TEXT,
    dw_raw_payload JSONB,
    dw_quarantined_ts_utc TIMESTAMPTZ DEFAULT NOW()
);
