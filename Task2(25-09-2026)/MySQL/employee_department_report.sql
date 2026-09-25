-- ============================================
-- EMPLOYEE AND DEPARTMENT REPORT
-- ============================================

USE movie_booking_db;

-- DEPARTMENTS TABLE

CREATE TABLE departments (
    department_id INT AUTO_INCREMENT,
    department_name VARCHAR(100) NOT NULL,
    CONSTRAINT pk_departments
        PRIMARY KEY (department_id),
    CONSTRAINT uq_department_name
        UNIQUE (department_name)
);

-- EMPLOYEES TABLE

CREATE TABLE employees (
    employee_id INT AUTO_INCREMENT,
    employee_name VARCHAR(100) NOT NULL,
    email VARCHAR(150) NOT NULL,
    salary DECIMAL(10,2) NOT NULL,
    department_id INT NOT NULL,

    CONSTRAINT pk_employees
        PRIMARY KEY (employee_id),

    CONSTRAINT uq_employee_email
        UNIQUE (email),

    CONSTRAINT chk_employee_salary
        CHECK (salary > 0),

    CONSTRAINT fk_employee_department
        FOREIGN KEY (department_id)
        REFERENCES departments(department_id)
        ON DELETE RESTRICT
);

-- INSERT DEPARTMENTS

INSERT INTO departments
(department_name)
VALUES
('Management'),
('IT'),
('Booking'),
('Finance'),
('Customer Service');

-- INSERT EMPLOYEES

INSERT INTO employees
(employee_name, email, salary, department_id)
VALUES
('Rahul', 'rahul@moviebooking.com', 60000.00, 2),
('Arun', 'arun@moviebooking.com', 45000.00, 3),
('Kiran', 'kiran@moviebooking.com', 75000.00, 1),
('Priya', 'priya@moviebooking.com', 55000.00, 4),
('Suresh', 'suresh@moviebooking.com', 90000.00, 1),
('Anil', 'anil@moviebooking.com', 40000.00, 5),
('Rahul', 'rahul2@moviebooking.com', 50000.00, 3),
('Vijay', 'vijay@moviebooking.com', 85000.00, 2),
('Ravi', 'ravi@moviebooking.com', 35000.00, 4),
('Manoj', 'manoj@moviebooking.com', 70000.00, 3);

-- VIEW DEPARTMENTS

SELECT *
FROM departments;


-- VIEW EMPLOYEES

SELECT *
FROM employees;

-- INNER JOIN

SELECT
    e.employee_id,
    e.employee_name,
    e.salary,
    d.department_id,
    d.department_name
FROM employees e
INNER JOIN departments d
    ON e.department_id = d.department_id;

-- LEFT JOIN

SELECT
    e.employee_id,
    e.employee_name,
    e.salary,
    COALESCE(
        d.department_name,
        'Not Assigned'
    ) AS department_name
FROM employees e
LEFT JOIN departments d
    ON e.department_id = d.department_id;

-- DEPARTMENT-WISE REPORT

SELECT
    d.department_id,
    d.department_name,
    COUNT(e.employee_id) AS employee_count,
    COALESCE(SUM(e.salary), 0) AS total_salary,
    COALESCE(AVG(e.salary), 0) AS average_salary
FROM departments d
LEFT JOIN employees e
    ON d.department_id = e.department_id
GROUP BY
    d.department_id,
    d.department_name;

-- DEPARTMENTS HAVING MORE THAN 2 EMPLOYEES

SELECT
    d.department_id,
    d.department_name,
    COUNT(e.employee_id) AS employee_count
FROM departments d
INNER JOIN employees e
    ON d.department_id = e.department_id
GROUP BY
    d.department_id,
    d.department_name
HAVING COUNT(e.employee_id) > 2;