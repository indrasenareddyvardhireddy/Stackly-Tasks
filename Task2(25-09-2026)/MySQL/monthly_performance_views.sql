-- ============================================
-- MONTHLY PERFORMANCE REPORTS
-- ============================================

USE movie_booking_db;


-- VIEW 1: MONTHLY SALES PERFORMANCE

CREATE VIEW monthly_sales_performance AS
SELECT
    YEAR(sale_date) AS sales_year,
    MONTH(sale_date) AS sales_month,
    COUNT(*) AS total_transactions,
    SUM(quantity) AS total_quantity,
    SUM(sale_amount) AS total_sales,
    AVG(sale_amount)
        AS average_transaction_value
FROM sales
GROUP BY
    YEAR(sale_date),
    MONTH(sale_date);

-- VIEW MONTHLY SALES PERFORMANCE

SELECT *
FROM monthly_sales_performance;

-- VIEW 2: MONTHLY PRODUCT PERFORMANCE

CREATE VIEW monthly_product_performance AS
SELECT
    p.product_id,
    p.product_name,
    YEAR(s.sale_date) AS sales_year,
    MONTH(s.sale_date) AS sales_month,
    SUM(s.quantity) AS quantity_sold,
    SUM(s.sale_amount) AS total_sales
FROM products p
INNER JOIN sales s
    ON p.product_id = s.product_id
GROUP BY
    p.product_id,
    p.product_name,
    YEAR(s.sale_date),
    MONTH(s.sale_date);

-- VIEW MONTHLY PRODUCT PERFORMANCE

SELECT *
FROM monthly_product_performance;

-- VIEW 3: PRODUCT SALES SUMMARY

CREATE VIEW product_sales_summary AS
SELECT
    p.product_id,
    p.product_name,
    p.price,
    p.quantity AS available_quantity,
    COALESCE(
        SUM(s.quantity),
        0
    ) AS total_quantity_sold,
    COALESCE(
        SUM(s.sale_amount),
        0
    ) AS total_sales
FROM products p
LEFT JOIN sales s
    ON p.product_id = s.product_id
GROUP BY
    p.product_id,
    p.product_name,
    p.price,
    p.quantity;

--VIEW PRODUCT SALES SUMMARY

SELECT *
FROM product_sales_summary;