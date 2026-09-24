-- ============================================================
-- CRUD operations on Book records
-- ============================================================

USE library_db;

-- CREATE / INSERT
INSERT INTO Books
(Book_Name, Author_Name, Category, Published_Year, Quantity)
VALUES
('Learning SQL', 'Alan Beaulieu', 'Database', 2020, 3);

-- READ / SELECT all books
SELECT * FROM Books;

-- READ / SELECT one book
SELECT *
FROM Books
WHERE Book_ID = 1;

-- READ / SELECT books by category
SELECT *
FROM Books
WHERE Category = 'Programming';

-- UPDATE
UPDATE Books
SET Quantity = 5
WHERE Book_ID = 2;

-- UPDATE multiple columns
UPDATE Books
SET Book_Name = 'Python Crash Course - Updated',
    Quantity = 7
WHERE Book_ID = 5;

-- DELETE
DELETE FROM Books
WHERE Book_ID = 6;

-- Verify records
SELECT * FROM Books;
