-- Seed 18 source table configurations
INSERT INTO ctl.ctl_table_config (source_table, extraction_pattern, watermark_column, lookback_days, primary_key, expected_rows, is_active)
VALUES
    ('customer', 'E1', 'updated_at', 7, 'customer_id', 10000, true),
    ('customer_address', 'E1', 'updated_at', 7, 'address_id', 15000, true),
    ('restaurant', 'E1', 'updated_at', 7, 'restaurant_id', 500, true),
    ('restaurant_owner', 'E1', 'updated_at', 7, 'owner_id', 500, true),
    ('menu_category', 'E3', NULL, 0, 'category_id', 2000, true),
    ('menu_item', 'E1', 'updated_at', 7, 'menu_item_id', 20000, true),
    ('delivery_partner', 'E1', 'updated_at', 7, 'partner_id', 1000, true),
    ('order_header', 'E1', 'updated_at', 7, 'order_id', 100000, true),
    ('order_item', 'E2', 'order_item_id', 0, 'order_item_id', 250000, true),
    ('payment_attempt', 'E1', 'created_at', 7, 'attempt_id', 120000, true),
    ('order_payment', 'E1', 'updated_at', 7, 'payment_id', 100000, true),
    ('order_delivery', 'E1', 'updated_at', 7, 'delivery_id', 100000, true),
    ('delivery_status_history', 'E2', 'history_id', 0, 'history_id', 300000, true),
    ('order_review', 'E1', 'created_at', 7, 'review_id', 50000, true),
    ('restaurant_review', 'E1', 'created_at', 7, 'review_id', 20000, true),
    ('cart_item', 'E3', NULL, 0, 'cart_item_id', 15000, true),
    ('discount_code', 'E5', NULL, 0, 'code_id', 100, true),
    ('promotion', 'E5', NULL, 0, 'promotion_id', 50, true)
ON CONFLICT (source_table) DO UPDATE SET
    extraction_pattern = EXCLUDED.extraction_pattern,
    watermark_column = EXCLUDED.watermark_column,
    lookback_days = EXCLUDED.lookback_days,
    primary_key = EXCLUDED.primary_key,
    expected_rows = EXCLUDED.expected_rows,
    is_active = EXCLUDED.is_active;
