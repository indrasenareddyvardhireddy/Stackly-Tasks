import os

FILE_NAME = "library_books.txt"


def add_book():
    book_id = input("Enter Book ID: ")
    title = input("Enter Book Title: ")
    author = input("Enter Author Name: ")

    with open(FILE_NAME, "a") as file:
        file.write(f"{book_id},{title},{author}\n")

    print("Book added successfully.")


def view_books():
    if not os.path.exists(FILE_NAME):
        print("No books found.")
        return

    print("\n--- Library Books ---")

    with open(FILE_NAME, "r") as file:
        books = file.readlines()

        if not books:
            print("No books available.")
            return

        for book in books:
            book_id, title, author = book.strip().split(",")

            print(f"ID: {book_id}")
            print(f"Title: {title}")
            print(f"Author: {author}")
            print("-" * 30)


def search_book():
    search_id = input("Enter Book ID to search: ")

    if not os.path.exists(FILE_NAME):
        print("No books found.")
        return

    found = False

    with open(FILE_NAME, "r") as file:
        for book in file:
            book_id, title, author = book.strip().split(",")

            if book_id == search_id:
                print("\nBook Found")
                print(f"ID: {book_id}")
                print(f"Title: {title}")
                print(f"Author: {author}")
                found = True
                break

    if not found:
        print("Book not found.")


def delete_book():
    delete_id = input("Enter Book ID to delete: ")

    if not os.path.exists(FILE_NAME):
        print("No books found.")
        return

    books = []
    found = False

    with open(FILE_NAME, "r") as file:
        for book in file:
            book_id, title, author = book.strip().split(",")

            if book_id == delete_id:
                found = True
            else:
                books.append(book)

    with open(FILE_NAME, "w") as file:
        file.writelines(books)

    if found:
        print("Book deleted successfully.")
    else:
        print("Book not found.")


def main():
    while True:
        print("\n===== Library Management System =====")
        print("1. Add Book")
        print("2. View Books")
        print("3. Search Book")
        print("4. Delete Book")
        print("5. Exit")

        choice = input("Enter your choice: ")

        if choice == "1":
            add_book()
        elif choice == "2":
            view_books()
        elif choice == "3":
            search_book()
        elif choice == "4":
            delete_book()
        elif choice == "5":
            print("Thank you!")
            break
        else:
            print("Invalid choice.")


if __name__ == "__main__":
    main()