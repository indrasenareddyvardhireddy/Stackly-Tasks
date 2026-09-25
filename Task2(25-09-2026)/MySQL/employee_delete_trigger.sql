-- ============================================
-- EMPLOYEE DELETE TRIGGER
-- ============================================

USE movie_booking_db;

-- DELETE LOG TABLE

CREATE TABLE employee_delete_log (
    log_id INT AUTO_INCREMENT,
    employee_id INT,
    employee_name VARCHAR(100),
    salary DECIMAL(10,2),
    department_id INT,
    deleted_at TIMESTAMP
        DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_employee_delete_log
        PRIMARY KEY (log_id)
);


-- DELETE TRIGGER

DELIMITER $$

CREATE TRIGGER after_employee_delete
AFTER DELETE ON employees
FOR EACH ROW
BEGIN
    INSERT INTO employee_delete_log
    (
        employee_id,
        employee_name,
        salary,
        department_id
    )
    VALUES
    (
        OLD.employee_id,
        OLD.employee_name,
        OLD.salary,
        OLD.department_id
    );
END$$
DELIMITER ;

-- TESTING TRIGGER

DELETE FROM employees
WHERE employee_id = 10;

-- VIEW DELETE LOG

SELECT *
FROM employee_delete_log;

