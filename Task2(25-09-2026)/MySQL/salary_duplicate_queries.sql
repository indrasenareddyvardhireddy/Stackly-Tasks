-- ============================================
-- SALARY AND DUPLICATE RECORD QUERIES
-- ============================================

USE movie_booking_db;

-- TOP 3 HIGHEST SALARIES

SELECT DISTINCT salary FROM employees
ORDER BY salary DESC LIMIT 3;

-- TOP 3 EMPLOYEES BASED ON SALARY

SELECT
    employee_id, employee_name, salary
FROM employees ORDER BY salary DESC LIMIT 3;

-- SECOND HIGHEST SALARY

SELECT MAX(salary) AS second_highest_salary FROM employees
WHERE salary < (SELECT MAX(salary) FROM employees);

-- SECOND HIGHEST SALARY USING LIMIT

SELECT DISTINCT salary
FROM employees
ORDER BY salary DESC
LIMIT 1 OFFSET 1;


-- DUPLICATE EMPLOYEE NAMES

SELECT
    employee_name, COUNT(*) AS duplicate_count
FROM employees
GROUP BY employee_name
HAVING COUNT(*) > 1;


-- DUPLICATE EMAILS

SELECT
    email, COUNT(*) AS duplicate_count
FROM employees
GROUP BY email
HAVING COUNT(*) > 1;


-- DUPLICATE SALARIES

SELECT
    salary, COUNT(*) AS duplicate_count
FROM employees
GROUP BY salary
HAVING COUNT(*) > 1;