-- ============================================================
-- Real-Time Fraud Detection Pipeline - Flink SQL Queries
-- Run these in Confluent Cloud Flink SQL Workspace
-- ============================================================

-- ============================================================
-- STEP 1: Verify raw transaction data is flowing
-- ============================================================
SELECT * FROM `transactions_raw` LIMIT 10;


-- ============================================================
-- STEP 2: Create windowed user spending profile
-- Aggregates user transactions in 5-minute tumbling windows
-- to establish baseline spending patterns
-- ============================================================
CREATE TABLE user_spending_profile WITH (
    'kafka.partitions' = '6'
) AS
SELECT
    user_id,
    COUNT(*)              AS txn_count,
    SUM(amount)           AS total_amount,
    AVG(amount)           AS avg_amount,
    MAX(amount)           AS max_amount,
    MIN(amount)           AS min_amount,
    STDDEV_SAMP(amount)   AS stddev_amount,
    window_start,
    window_end
FROM TABLE(
    TUMBLE(
        TABLE `transactions_raw`,
        DESCRIPTOR(`$rowtime`),
        INTERVAL '5' MINUTES
    )
)
GROUP BY user_id, window_start, window_end;


-- ============================================================
-- STEP 3: Create fraud alerts table
-- Detects anomalies by comparing each transaction against the
-- user's rolling spending profile from the previous window.
-- ============================================================
CREATE TABLE fraud_alerts WITH (
    'kafka.partitions' = '6',
    'value.format' = 'avro-confluent'
) AS
SELECT
    t.transaction_id,
    t.user_id,
    t.amount,
    t.merchant,
    CAST(t.category AS STRING) AS category,
    t.location,
    -- Risk level classification
    CASE
        WHEN t.amount > COALESCE(p.avg_amount, 100) * 5 THEN 'CRITICAL'
        WHEN t.amount > COALESCE(p.avg_amount, 100) * 3 THEN 'HIGH'
        WHEN COALESCE(p.txn_count, 0) > 10             THEN 'MEDIUM'
        WHEN t.amount > 5000                            THEN 'HIGH'
        ELSE 'LOW'
    END AS risk_level,
    -- Anomaly type classification
    CASE
        WHEN t.amount > COALESCE(p.avg_amount, 100) * 5 THEN 'HIGH_AMOUNT'
        WHEN t.amount > COALESCE(p.avg_amount, 100) * 3 THEN 'HIGH_AMOUNT'
        WHEN COALESCE(p.txn_count, 0) > 10              THEN 'HIGH_VELOCITY'
        WHEN t.amount > 5000                             THEN 'THRESHOLD_BREACH'
        ELSE 'STATISTICAL_ANOMALY'
    END AS anomaly_type,
    -- Risk score (0-100)
    LEAST(100.0, GREATEST(0.0,
        CASE
            WHEN COALESCE(p.avg_amount, 0) > 0
                THEN (t.amount / p.avg_amount) * 20
            ELSE t.amount / 50.0
        END
    )) AS risk_score,
    COALESCE(p.avg_amount, 0.0) AS avg_user_amount,
    COALESCE(p.txn_count, 0) AS user_txn_count,
    CURRENT_TIMESTAMP AS flagged_at
FROM `transactions_raw` t
LEFT JOIN user_spending_profile p
    ON t.user_id = p.user_id
WHERE
    -- Flag high-amount transactions relative to user's average
    t.amount > COALESCE(p.avg_amount, 100) * 3
    -- Flag high-velocity spending (many txns in 5 min)
    OR COALESCE(p.txn_count, 0) > 10
    -- Flag absolute threshold breaches
    OR t.amount > 5000;


-- ============================================================
-- STEP 4: (Optional) Create enriched transactions view
-- Adds risk context to ALL transactions for the dashboard
-- ============================================================
CREATE TABLE transactions_enriched WITH (
    'kafka.partitions' = '6'
) AS
SELECT
    t.transaction_id,
    t.user_id,
    t.amount,
    t.merchant,
    CAST(t.category AS STRING) AS category,
    t.location,
    CAST(t.card_type AS STRING) AS card_type,
    t.is_online,
    CASE
        WHEN t.amount > COALESCE(p.avg_amount, 100) * 3 THEN true
        WHEN COALESCE(p.txn_count, 0) > 10              THEN true
        WHEN t.amount > 5000                             THEN true
        ELSE false
    END AS is_flagged,
    COALESCE(p.avg_amount, 0.0) AS user_avg_amount,
    COALESCE(p.txn_count, 0) AS user_window_txn_count
FROM `transactions_raw` t
LEFT JOIN user_spending_profile p
    ON t.user_id = p.user_id;


-- ============================================================
-- STEP 5: Monitoring queries (run ad-hoc)
-- ============================================================

-- Check fraud alert rate
SELECT
    risk_level,
    COUNT(*) AS alert_count,
    AVG(risk_score) AS avg_risk_score
FROM fraud_alerts
GROUP BY risk_level;

-- Check top flagged users
SELECT
    user_id,
    COUNT(*) AS alert_count,
    SUM(amount) AS total_flagged_amount
FROM fraud_alerts
GROUP BY user_id
ORDER BY alert_count DESC
LIMIT 10;
