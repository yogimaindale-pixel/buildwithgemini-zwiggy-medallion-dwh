-- Gold Layer Fact & Mart DDLs

-- 1. fact_order
CREATE TABLE IF NOT EXISTS gold.fact_order (
    order_sk BIGSERIAL PRIMARY KEY,
    order_id BIGINT NOT NULL,
    customer_sk BIGINT NOT NULL REFERENCES gold.dim_customer(customer_sk),
    restaurant_sk BIGINT NOT NULL REFERENCES gold.dim_restaurant(restaurant_sk),
    order_date_sk INT NOT NULL REFERENCES gold.dim_date(date_sk),
    order_time_sk INT NOT NULL REFERENCES gold.dim_time(time_sk),
    flag_sk BIGINT REFERENCES gold.dim_order_flag(flag_sk),
    order_status VARCHAR(50),
    total_amount NUMERIC(12,2),
    discount_amount NUMERIC(12,2),
    delivery_fee NUMERIC(12,2),
    cohort_id VARCHAR(10),
    dw_batch_id BIGINT NOT NULL,
    dw_ingest_ts_utc TIMESTAMPTZ DEFAULT NOW()
);

-- 2. fact_order_item
CREATE TABLE IF NOT EXISTS gold.fact_order_item (
    order_item_sk BIGSERIAL PRIMARY KEY,
    order_item_id BIGINT NOT NULL,
    order_sk BIGINT NOT NULL REFERENCES gold.fact_order(order_sk),
    menu_item_sk BIGINT NOT NULL REFERENCES gold.dim_menu_item(menu_item_sk),
    quantity INT,
    unit_price NUMERIC(12,2),
    item_total NUMERIC(12,2),
    dw_batch_id BIGINT NOT NULL,
    dw_ingest_ts_utc TIMESTAMPTZ DEFAULT NOW()
);

-- 3. fact_payment_attempt
CREATE TABLE IF NOT EXISTS gold.fact_payment_attempt (
    attempt_sk BIGSERIAL PRIMARY KEY,
    attempt_id BIGINT NOT NULL,
    order_sk BIGINT NOT NULL REFERENCES gold.fact_order(order_sk),
    conformed_method VARCHAR(50),
    status VARCHAR(50),
    amount NUMERIC(12,2),
    created_date_sk INT REFERENCES gold.dim_date(date_sk),
    dw_batch_id BIGINT NOT NULL,
    dw_ingest_ts_utc TIMESTAMPTZ DEFAULT NOW()
);

-- 4. fact_payment
CREATE TABLE IF NOT EXISTS gold.fact_payment (
    payment_sk BIGSERIAL PRIMARY KEY,
    payment_id BIGINT NOT NULL,
    order_sk BIGINT NOT NULL REFERENCES gold.fact_order(order_sk),
    payment_method VARCHAR(50),
    status VARCHAR(50),
    amount NUMERIC(12,2),
    payment_date_sk INT REFERENCES gold.dim_date(date_sk),
    dw_batch_id BIGINT NOT NULL,
    dw_ingest_ts_utc TIMESTAMPTZ DEFAULT NOW()
);

-- 5. fact_delivery
CREATE TABLE IF NOT EXISTS gold.fact_delivery (
    delivery_sk BIGSERIAL PRIMARY KEY,
    delivery_id BIGINT NOT NULL,
    order_sk BIGINT NOT NULL REFERENCES gold.fact_order(order_sk),
    partner_sk BIGINT NOT NULL REFERENCES gold.dim_delivery_partner(partner_sk),
    delivery_status VARCHAR(50),
    assigned_at TIMESTAMPTZ,
    delivered_at TIMESTAMPTZ,
    delivery_time_minutes NUMERIC(8,2),
    dw_batch_id BIGINT NOT NULL,
    dw_ingest_ts_utc TIMESTAMPTZ DEFAULT NOW()
);

-- 6. fact_review
CREATE TABLE IF NOT EXISTS gold.fact_review (
    review_sk BIGSERIAL PRIMARY KEY,
    review_id BIGINT NOT NULL,
    order_sk BIGINT REFERENCES gold.fact_order(order_sk),
    restaurant_sk BIGINT REFERENCES gold.dim_restaurant(restaurant_sk),
    customer_sk BIGINT REFERENCES gold.dim_customer(customer_sk),
    rating INT,
    review_text TEXT,
    dw_batch_id BIGINT NOT NULL,
    dw_ingest_ts_utc TIMESTAMPTZ DEFAULT NOW()
);

-- 7. fact_cart_item
CREATE TABLE IF NOT EXISTS gold.fact_cart_item (
    cart_item_sk BIGSERIAL PRIMARY KEY,
    cart_item_id BIGINT NOT NULL,
    customer_sk BIGINT NOT NULL REFERENCES gold.dim_customer(customer_sk),
    menu_item_sk BIGINT NOT NULL REFERENCES gold.dim_menu_item(menu_item_sk),
    quantity INT,
    dw_batch_id BIGINT NOT NULL,
    dw_ingest_ts_utc TIMESTAMPTZ DEFAULT NOW()
);

-- 8. fact_order_fulfilment
CREATE TABLE IF NOT EXISTS gold.fact_order_fulfilment (
    fulfilment_sk BIGSERIAL PRIMARY KEY,
    order_sk BIGINT NOT NULL REFERENCES gold.fact_order(order_sk),
    partner_sk BIGINT REFERENCES gold.dim_delivery_partner(partner_sk),
    is_delivered BOOLEAN,
    is_on_time BOOLEAN,
    fulfilment_duration_minutes NUMERIC(8,2),
    dw_batch_id BIGINT NOT NULL,
    dw_ingest_ts_utc TIMESTAMPTZ DEFAULT NOW()
);

-- 9. Mart: mart_daily_business_summary
CREATE TABLE IF NOT EXISTS gold.mart_daily_business_summary (
    summary_date DATE PRIMARY KEY,
    total_orders INT DEFAULT 0,
    total_revenue NUMERIC(14,2) DEFAULT 0,
    total_discounts NUMERIC(14,2) DEFAULT 0,
    active_customers INT DEFAULT 0,
    dw_batch_id BIGINT NOT NULL,
    updated_ts_utc TIMESTAMPTZ DEFAULT NOW()
);

-- 10. Mart: mart_daily_restaurant_performance
CREATE TABLE IF NOT EXISTS gold.mart_daily_restaurant_performance (
    summary_date DATE,
    restaurant_id BIGINT,
    total_orders INT DEFAULT 0,
    total_revenue NUMERIC(14,2) DEFAULT 0,
    avg_rating NUMERIC(3,2),
    dw_batch_id BIGINT NOT NULL,
    updated_ts_utc TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (summary_date, restaurant_id)
);

-- 11. Mart: mart_daily_delivery_performance
CREATE TABLE IF NOT EXISTS gold.mart_daily_delivery_performance (
    summary_date DATE,
    partner_id BIGINT,
    total_deliveries INT DEFAULT 0,
    on_time_deliveries INT DEFAULT 0,
    avg_delivery_time_minutes NUMERIC(8,2),
    dw_batch_id BIGINT NOT NULL,
    updated_ts_utc TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (summary_date, partner_id)
);
