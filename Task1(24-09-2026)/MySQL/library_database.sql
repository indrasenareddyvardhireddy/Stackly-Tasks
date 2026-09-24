-- ============================================================
-- Library Management System
-- Database and table creation
-- ============================================================

CREATE DATABASE library_db;
USE library_db;

CREATE TABLE Books (
    Book_ID INT PRIMARY KEY AUTO_INCREMENT,
    Book_Name VARCHAR(150) NOT NULL,
    Author_Name VARCHAR(100) NOT NULL,
    Category VARCHAR(50) NOT NULL,
    Published_Year YEAR,
    Quantity INT NOT NULL DEFAULT 1,
    CONSTRAINT chk_book_quantity CHECK (Quantity >= 0)
);

CREATE TABLE Members (
    Member_ID INT PRIMARY KEY AUTO_INCREMENT,
    Member_Name VARCHAR(100) NOT NULL,
    Email VARCHAR(150) NOT NULL UNIQUE,
    Phone VARCHAR(15) UNIQUE,
    Join_Date DATE NOT NULL
);

CREATE TABLE Borrow_Records (
    Borrow_ID INT PRIMARY KEY AUTO_INCREMENT,
    Book_ID INT NOT NULL,
    Member_ID INT NOT NULL,
    Borrow_Date DATE NOT NULL,
    Return_Date DATE NULL,
    Status ENUM('Borrowed', 'Returned') NOT NULL DEFAULT 'Borrowed',

    CONSTRAINT fk_borrow_book
        FOREIGN KEY (Book_ID)
        REFERENCES Books(Book_ID)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,

    CONSTRAINT fk_borrow_member
        FOREIGN KEY (Member_ID)
        REFERENCES Members(Member_ID)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,

    CONSTRAINT chk_return_date
        CHECK (Return_Date IS NULL OR Return_Date >= Borrow_Date)
);

-- Sample book records
INSERT INTO Books
(Book_Name, Author_Name, Category, Published_Year, Quantity)
VALUES
('The Alchemist', 'Paulo Coelho', 'Fiction', 1988, 5),
('Clean Code', 'Robert C. Martin', 'Programming', 2008, 3),
('Atomic Habits', 'James Clear', 'Self Help', 2018, 4),
('Database System Concepts', 'Abraham Silberschatz', 'Database', 2019, 2),
('Python Crash Course', 'Eric Matthes', 'Programming', 2019, 6);

-- Sample members
INSERT INTO Members
(Member_Name, Email, Phone, Join_Date)
VALUES
('Rahul Kumar', 'rahul@example.com', '9876543210', '2026-01-10'),
('Anjali Sharma', 'anjali@example.com', '9876543211', '2026-02-15'),
('Vikram Reddy', 'vikram@example.com', '9876543212', '2026-03-20');

-- Sample borrowing records
INSERT INTO Borrow_Records
(Book_ID, Member_ID, Borrow_Date, Return_Date, Status)
VALUES
(1, 1, '2026-09-01', '2026-09-10', 'Returned'),
(2, 2, '2026-09-05', NULL, 'Borrowed'),
(3, 3, '2026-09-07', '2026-09-15', 'Returned'),
(5, 1, '2026-09-12', NULL, 'Borrowed');
