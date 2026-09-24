-- ============================================================
-- JOIN, GROUP BY, ORDER BY and Aggregate Functions
-- ============================================================

USE library_db;

-- 1. INNER JOIN:
-- Show borrowed books with member details.
SELECT
    br.Borrow_ID,
    b.Book_Name,
    m.Member_Name,
    br.Borrow_Date,
    br.Return_Date,
    br.Status
FROM Borrow_Records br
INNER JOIN Books b
    ON br.Book_ID = b.Book_ID
INNER JOIN Members m
    ON br.Member_ID = m.Member_ID;

-- 2. LEFT JOIN:
-- Show every book and borrowing records if available.
SELECT
    b.Book_ID,
    b.Book_Name,
    br.Borrow_ID,
    br.Status
FROM Books b
LEFT JOIN Borrow_Records br
    ON b.Book_ID = br.Book_ID;

-- 3. ORDER BY:
-- Books ordered by name.
SELECT *
FROM Books
ORDER BY Book_Name ASC;

-- Books ordered by quantity from highest to lowest.
SELECT *
FROM Books
ORDER BY Quantity DESC;

-- 4. Aggregate Functions:
-- Total number of books/rows.
SELECT COUNT(*) AS Total_Book_Titles
FROM Books;

-- Total available copies.
SELECT SUM(Quantity) AS Total_Available_Copies
FROM Books;

-- Average quantity per book title.
SELECT AVG(Quantity) AS Average_Quantity
FROM Books;

-- Maximum quantity.
SELECT MAX(Quantity) AS Maximum_Quantity
FROM Books;

-- Minimum quantity.
SELECT MIN(Quantity) AS Minimum_Quantity
FROM Books;

-- 5. GROUP BY:
-- Number of book titles in each category.
SELECT
    Category,
    COUNT(*) AS Number_Of_Books
FROM Books
GROUP BY Category;

-- Total copies available in each category.
SELECT
    Category,
    SUM(Quantity) AS Total_Copies
FROM Books
GROUP BY Category
ORDER BY Total_Copies DESC;

-- 6. GROUP BY with JOIN:
-- Number of times each member borrowed a book.
SELECT
    m.Member_ID,
    m.Member_Name,
    COUNT(br.Borrow_ID) AS Borrow_Count
FROM Members m
LEFT JOIN Borrow_Records br
    ON m.Member_ID = br.Member_ID
GROUP BY m.Member_ID, m.Member_Name
ORDER BY Borrow_Count DESC;

-- 7. HAVING:
-- Categories having more than one book title.
SELECT
    Category,
    COUNT(*) AS Number_Of_Books
FROM Books
GROUP BY Category
HAVING COUNT(*) > 1;
