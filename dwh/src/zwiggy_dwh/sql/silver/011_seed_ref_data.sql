-- Seed Silver Reference Data

-- Seed ref_cohort_rule
INSERT INTO silver.ref_cohort_rule (cohort_id, min_order_id, max_order_id, description)
VALUES
    ('COHORT_A', 1, 50000, 'Legacy initial cohort orders'),
    ('COHORT_B', 50001, 999999999, 'Modern cohort orders')
ON CONFLICT (cohort_id) DO UPDATE SET
    min_order_id = EXCLUDED.min_order_id,
    max_order_id = EXCLUDED.max_order_id,
    description = EXCLUDED.description;

-- Seed ref_payment_method_map
INSERT INTO silver.ref_payment_method_map (raw_payment_method, conformed_payment_method, conformed_category)
VALUES
    ('credit_card', 'CREDIT_CARD', 'CARD'),
    ('debit_card', 'DEBIT_CARD', 'CARD'),
    ('card', 'CREDIT_CARD', 'CARD'),
    ('upi', 'UPI', 'DIGITAL'),
    ('net_banking', 'NET_BANKING', 'DIGITAL'),
    ('netbanking', 'NET_BANKING', 'DIGITAL'),
    ('wallet', 'WALLET', 'DIGITAL'),
    ('cash_on_delivery', 'CASH_ON_DELIVERY', 'CASH'),
    ('cod', 'CASH_ON_DELIVERY', 'CASH'),
    ('pay_later', 'BNPL', 'CREDIT')
ON CONFLICT (raw_payment_method) DO UPDATE SET
    conformed_payment_method = EXCLUDED.conformed_payment_method,
    conformed_category = EXCLUDED.conformed_category;
