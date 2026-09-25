-- ============================================
-- PRODUCT SALES ANALYSIS
-- ============================================

USE movie_booking_db;

-- PRODUCTS TABLE

CREATE TABLE products (
    product_id INT AUTO_INCREMENT,
    product_name VARCHAR(100) NOT NULL,
    price DECIMAL(10,2) NOT NULL,
    quantity INT NOT NULL DEFAULT 0,
    CONSTRAINT pk_products
        PRIMARY KEY (product_id),
    CONSTRAINT chk_product_price
        CHECK (price >= 0),
    CONSTRAINT chk_product_quantity
        CHECK (quantity >= 0)
);

-- SALES TABLE

CREATE TABLE sales (
    sale_id INT AUTO_INCREMENT,
    product_id INT NOT NULL,
    quantity INT NOT NULL,
    sale_amount DECIMAL(10,2) NOT NULL,
    sale_date DATE NOT NULL,

    CONSTRAINT pk_sales
        PRIMARY KEY (sale_id),

    CONSTRAINT fk_sales_product
        FOREIGN KEY (product_id)
        REFERENCES products(product_id)
        ON DELETE RESTRICT,

    CONSTRAINT chk_sales_quantity
        CHECK (quantity > 0),

    CONSTRAINT chk_sales_amount
        CHECK (sale_amount >= 0)
);


-- SAMPLE PRODUCTS

INSERT INTO products
(product_name, price, quantity)
VALUES
('Movie Ticket', 200.00, 100),
('Popcorn', 150.00, 200),
('Cold Drink', 100.00, 250),
('Nachos', 180.00, 150),
('Combo Meal', 350.00, 100);

-- SAMPLE SALES

INSERT INTO sales
(product_id, quantity, sale_amount, sale_date)
VALUES
(1, 10, 2000.00, '2026-09-01'),
(2, 20, 3000.00, '2026-09-02'),
(3, 15, 1500.00, '2026-09-05'),
(4, 8, 1440.00, '2026-09-10'),
(5, 5, 1750.00, '2026-09-15'),
(1, 15, 3000.00, '2026-09-20'),
(2, 10, 1500.00, '2026-09-21');


-- PRODUCTS ABOVE AVERAGE PRICE

SELECT *
FROM products
WHERE price > (
    SELECT AVG(price)
    FROM products
);

-- PRODUCTS THAT HAVE BEEN SOLD

SELECT *
FROM products
WHERE product_id IN (SELECT DISTINCT product_id FROM sales);

-- PRODUCTS THAT HAVE NEVER BEEN SOLD

SELECT *
FROM products p
WHERE NOT EXISTS ( SELECT 1 FROM sales s WHERE s.product_id = p.product_id);

-- TOTAL QUANTITY SOLD PER PRODUCT

SELECT
    p.product_id,
    p.product_name,
    (SELECT COALESCE(SUM(s.quantity),0)
        FROM sales s
        WHERE s.product_id = p.product_id
    ) AS total_quantity_sold
FROM products p;

-- PRODUCTS WITH ABOVE-AVERAGE SALES

SELECT
    p.product_id,
    p.product_name,
    SUM(s.quantity) AS total_quantity
FROM products p
INNER JOIN sales s
    ON p.product_id = s.product_id
GROUP BY
    p.product_id,
    p.product_name
HAVING SUM(s.quantity) > (
    SELECT AVG(total_quantity)
    FROM (
        SELECT
            SUM(quantity) AS total_quantity
        FROM sales
        GROUP BY product_id
    ) AS product_totals
);