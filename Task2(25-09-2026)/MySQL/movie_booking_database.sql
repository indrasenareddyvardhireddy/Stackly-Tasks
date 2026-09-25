-- ============================================
-- MOVIE BOOKING DATABASE
-- ============================================

CREATE DATABASE movie_booking_db;

USE movie_booking_db;



-- MOVIES TABLE


CREATE TABLE movies (
    movie_id INT AUTO_INCREMENT,
    title VARCHAR(150) NOT NULL,
    genre VARCHAR(50) NOT NULL,
    duration_minutes INT NOT NULL,
    release_date DATE NOT NULL,
    CONSTRAINT pk_movies
        PRIMARY KEY (movie_id),
    CONSTRAINT chk_movie_duration
        CHECK (duration_minutes > 0)
);



-- CUSTOMERS TABLE

CREATE TABLE customers (
    customer_id INT AUTO_INCREMENT,
    customer_name VARCHAR(100) NOT NULL,
    email VARCHAR(150) NOT NULL,
    phone VARCHAR(20),
    CONSTRAINT pk_customers
        PRIMARY KEY (customer_id),
    CONSTRAINT uq_customer_email
        UNIQUE (email)
);


-- THEATRES TABLE

CREATE TABLE theatres (
    theatre_id INT AUTO_INCREMENT,
    theatre_name VARCHAR(100) NOT NULL,
    location VARCHAR(150) NOT NULL,
    CONSTRAINT pk_theatres
        PRIMARY KEY (theatre_id)
);


-- SCREENS TABLE

CREATE TABLE screens (
    screen_id INT AUTO_INCREMENT,
    theatre_id INT NOT NULL,
    screen_name VARCHAR(50) NOT NULL,
    total_seats INT NOT NULL,

    CONSTRAINT pk_screens
        PRIMARY KEY (screen_id),

    CONSTRAINT fk_screen_theatre
        FOREIGN KEY (theatre_id)
        REFERENCES theatres(theatre_id)
        ON DELETE RESTRICT,

    CONSTRAINT chk_screen_seats
        CHECK (total_seats > 0),

    CONSTRAINT uq_theatre_screen
        UNIQUE (theatre_id, screen_name)
);


-- SHOWS TABLE

CREATE TABLE shows (
    show_id INT AUTO_INCREMENT,
    movie_id INT NOT NULL,
    screen_id INT NOT NULL,
    show_date DATE NOT NULL,
    show_time TIME NOT NULL,
    ticket_price DECIMAL(10,2) NOT NULL,

    CONSTRAINT pk_shows
        PRIMARY KEY (show_id),

    CONSTRAINT fk_show_movie
        FOREIGN KEY (movie_id)
        REFERENCES movies(movie_id)
        ON DELETE RESTRICT,

    CONSTRAINT fk_show_screen
        FOREIGN KEY (screen_id)
        REFERENCES screens(screen_id)
        ON DELETE RESTRICT,

    CONSTRAINT chk_ticket_price
        CHECK (ticket_price > 0)
);


-- BOOKINGS TABLE

CREATE TABLE bookings (
    booking_id INT AUTO_INCREMENT,
    customer_id INT NOT NULL,
    show_id INT NOT NULL,
    booking_date DATETIME
        DEFAULT CURRENT_TIMESTAMP,
    total_amount DECIMAL(10,2) NOT NULL,
    status ENUM(
        'CONFIRMED',
        'CANCELLED'
    ) DEFAULT 'CONFIRMED',

    CONSTRAINT pk_bookings
        PRIMARY KEY (booking_id),

    CONSTRAINT fk_booking_customer
        FOREIGN KEY (customer_id)
        REFERENCES customers(customer_id)
        ON DELETE RESTRICT,

    CONSTRAINT fk_booking_show
        FOREIGN KEY (show_id)
        REFERENCES shows(show_id)
        ON DELETE RESTRICT,

    CONSTRAINT chk_booking_amount
        CHECK (total_amount >= 0)
);


-- BOOKING SEATS TABLE

CREATE TABLE booking_seats (
    booking_seat_id INT AUTO_INCREMENT,
    booking_id INT NOT NULL,
    seat_number VARCHAR(10) NOT NULL,

    CONSTRAINT pk_booking_seats
        PRIMARY KEY (booking_seat_id),

    CONSTRAINT fk_booking_seat_booking
        FOREIGN KEY (booking_id)
        REFERENCES bookings(booking_id)
        ON DELETE RESTRICT,

    CONSTRAINT uq_booking_seat
        UNIQUE (booking_id, seat_number)
);


-- SAMPLE MOVIES

INSERT INTO movies
(title, genre, duration_minutes, release_date)
VALUES
('Movie A', 'Action', 140, '2026-01-10'),
('Movie B', 'Drama', 125, '2026-02-15'),
('Movie C', 'Comedy', 110, '2026-03-20'),
('Movie D', 'Thriller', 130, '2026-04-05'),
('Movie E', 'Sci-Fi', 150, '2026-05-12');

-- SAMPLE CUSTOMERS

INSERT INTO customers
(customer_name, email, phone)
VALUES
('Rahul', 'rahul@gmail.com', '9876543210'),
('Arun', 'arun@gmail.com', '9876543211'),
('Kiran', 'kiran@gmail.com', '9876543212'),
('Priya', 'priya@gmail.com', '9876543213'),
('Suresh', 'suresh@gmail.com', '9876543214');

-- SAMPLE THEATRES

INSERT INTO theatres
(theatre_name, location)
VALUES
('PVR Central', 'Nellore'),
('INOX Mall', 'Nellore');

-- SAMPLE SCREENS

INSERT INTO screens
(theatre_id, screen_name, total_seats)
VALUES
(1, 'Screen 1', 100),
(1, 'Screen 2', 80),
(2, 'Screen 1', 120);

-- SAMPLE SHOWS

INSERT INTO shows
(movie_id, screen_id, show_date, show_time, ticket_price)
VALUES
(1, 1, '2026-09-25', '10:00:00', 200.00),
(2, 1, '2026-09-25', '14:00:00', 180.00),
(3, 2, '2026-09-25', '18:00:00', 150.00),
(4, 3, '2026-09-25', '21:00:00', 220.00),
(5, 2, '2026-09-26', '20:00:00', 250.00);

-- SAMPLE BOOKINGS

INSERT INTO bookings
(customer_id, show_id, total_amount, status)
VALUES
(1, 1, 400.00, 'CONFIRMED'),
(2, 2, 360.00, 'CONFIRMED'),
(3, 3, 300.00, 'CONFIRMED'),
(4, 4, 440.00, 'CANCELLED');

-- SAMPLE BOOKING SEATS

INSERT INTO booking_seats
(booking_id, seat_number)
VALUES
(1, 'A1'),
(1, 'A2'),
(2, 'B1'),
(2, 'B2'),
(3, 'C1'),
(3, 'C2'),
(4, 'D1'),
(4, 'D2');