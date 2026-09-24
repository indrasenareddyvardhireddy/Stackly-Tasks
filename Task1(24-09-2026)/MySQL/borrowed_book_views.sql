-- ============================================================
-- SQL Views for borrowed book reports
-- ============================================================

USE library_db;

-- View 1: Complete borrowed book report
CREATE VIEW borrowed_book_report AS
SELECT
    br.Borrow_ID,
    b.Book_ID,
    b.Book_Name,
    b.Author_Name,
    b.Category,
    m.Member_ID,
    m.Member_Name,
    m.Email,
    br.Borrow_Date,
    br.Return_Date,
    br.Status
FROM Borrow_Records br
INNER JOIN Books b
    ON br.Book_ID = b.Book_ID
INNER JOIN Members m
    ON br.Member_ID = m.Member_ID;

-- View 2: Currently borrowed books
CREATE VIEW currently_borrowed_books AS
SELECT
    br.Borrow_ID,
    b.Book_Name,
    m.Member_Name,
    br.Borrow_Date,
    br.Status
FROM Borrow_Records br
INNER JOIN Books b
    ON br.Book_ID = b.Book_ID
INNER JOIN Members m
    ON br.Member_ID = m.Member_ID
WHERE br.Status = 'Borrowed';

-- View 3: Borrowing summary by member
CREATE VIEW member_borrow_summary AS
SELECT
    m.Member_ID,
    m.Member_Name,
    COUNT(br.Borrow_ID) AS Total_Borrowings,
    SUM(
        CASE
            WHEN br.Status = 'Borrowed' THEN 1
            ELSE 0
        END
    ) AS Currently_Borrowed
FROM Members m
LEFT JOIN Borrow_Records br
    ON m.Member_ID = br.Member_ID
GROUP BY m.Member_ID, m.Member_Name;

-- Test the views
SELECT * FROM borrowed_book_report;
SELECT * FROM currently_borrowed_books;
SELECT * FROM member_borrow_summary;
