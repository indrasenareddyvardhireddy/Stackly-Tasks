-- =========================================================
-- LIBRARY MANAGEMENT SYSTEM DATABASE
-- MySQL
-- =========================================================

-- Create database
CREATE DATABASE IF NOT EXISTS library_db;

USE library_db;


-- =========================================================
-- 1. USERS TABLE
-- =========================================================

CREATE TABLE IF NOT EXISTS users (
    user_id INT PRIMARY KEY AUTO_INCREMENT,

    username VARCHAR(100) NOT NULL UNIQUE,

    email VARCHAR(150) NOT NULL UNIQUE,

    password_hash VARCHAR(255) NOT NULL,

    role VARCHAR(20) NOT NULL DEFAULT 'User',

    is_active BOOLEAN NOT NULL DEFAULT TRUE,

    CONSTRAINT chk_user_role
        CHECK (role IN ('Admin', 'User'))
);


-- =========================================================
-- 2. CATEGORIES TABLE
-- =========================================================

CREATE TABLE IF NOT EXISTS categories (
    category_id INT PRIMARY KEY AUTO_INCREMENT,

    category_name VARCHAR(100) NOT NULL UNIQUE,

    description VARCHAR(255)
);


-- =========================================================
-- 3. MEMBERS TABLE
-- =========================================================

CREATE TABLE IF NOT EXISTS members (
    member_id INT PRIMARY KEY AUTO_INCREMENT,

    -- Each User can have only one Member record
    user_id INT UNIQUE,

    name VARCHAR(100) NOT NULL,

    email VARCHAR(150) NOT NULL UNIQUE,

    phone VARCHAR(15) NOT NULL,

    address VARCHAR(255) NOT NULL,

    membership_date DATE NOT NULL,

    is_active BOOLEAN NOT NULL DEFAULT TRUE,

    CONSTRAINT fk_member_user
        FOREIGN KEY (user_id)
        REFERENCES users(user_id)
);


-- =========================================================
-- 4. BOOKS TABLE
-- =========================================================

CREATE TABLE IF NOT EXISTS books (
    book_id INT PRIMARY KEY AUTO_INCREMENT,

    title VARCHAR(200) NOT NULL,

    author VARCHAR(150) NOT NULL,

    isbn VARCHAR(20) NOT NULL UNIQUE,

    category_id INT NOT NULL,

    total_copies INT NOT NULL,

    available_copies INT NOT NULL,

    published_year INT,

    CONSTRAINT fk_book_category
        FOREIGN KEY (category_id)
        REFERENCES categories(category_id),

    CONSTRAINT chk_total_copies
        CHECK (total_copies >= 0),

    CONSTRAINT chk_available_copies
        CHECK (available_copies >= 0),

    CONSTRAINT chk_available_not_greater
        CHECK (available_copies <= total_copies)
);


-- =========================================================
-- 5. BORROW RECORDS TABLE
-- =========================================================

CREATE TABLE IF NOT EXISTS borrow_records (
    borrow_id INT PRIMARY KEY AUTO_INCREMENT,

    book_id INT NOT NULL,

    member_id INT NOT NULL,

    borrow_date DATE NOT NULL,

    due_date DATE NOT NULL,

    return_date DATE NULL,

    status VARCHAR(20) NOT NULL DEFAULT 'Borrowed',

    CONSTRAINT fk_borrow_book
        FOREIGN KEY (book_id)
        REFERENCES books(book_id),

    CONSTRAINT fk_borrow_member
        FOREIGN KEY (member_id)
        REFERENCES members(member_id),

    CONSTRAINT chk_borrow_status
        CHECK (
            status IN (
                'Borrowed',
                'Returned',
                'Overdue'
            )
        )
);


-- =========================================================
-- INDEXES
-- =========================================================

CREATE INDEX idx_books_title
ON books(title);

CREATE INDEX idx_books_author
ON books(author);

CREATE INDEX idx_books_category
ON books(category_id);

CREATE INDEX idx_members_user
ON members(user_id);

CREATE INDEX idx_borrow_book
ON borrow_records(book_id);

CREATE INDEX idx_borrow_member
ON borrow_records(member_id);

CREATE INDEX idx_borrow_status
ON borrow_records(status);


-- =========================================================
-- SAMPLE CATEGORIES
-- =========================================================

INSERT IGNORE INTO categories
(category_name, description)
VALUES
('Programming', 'Programming and software development books'),
('Database', 'Database and SQL books'),
('Web Development', 'Web development books'),
('Artificial Intelligence', 'AI and machine learning books'),
('Computer Science', 'Computer science reference books');


-- =========================================================
-- SAMPLE BOOKS
-- =========================================================

INSERT IGNORE INTO books
(title, author, isbn, category_id, total_copies, available_copies, published_year)
VALUES
(
    'Python Programming',
    'John Smith',
    '9781000000001',
    1,
    5,
    5,
    2024
),
(
    'SQL Fundamentals',
    'Robert Brown',
    '9781000000002',
    2,
    4,
    4,
    2023
),
(
    'Web Development Basics',
    'David Miller',
    '9781000000003',
    3,
    3,
    3,
    2024
),
(
    'Artificial Intelligence',
    'Andrew Wilson',
    '9781000000004',
    4,
    5,
    5,
    2025
),
(
    'Computer Science Fundamentals',
    'James Anderson',
    '9781000000005',
    5,
    4,
    4,
    2023
);


-- =========================================================
-- DATABASE COMPLETE
-- =========================================================