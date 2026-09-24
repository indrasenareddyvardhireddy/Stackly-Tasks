import mysql.connector


def connect_database():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="root",
        database="product_db"
    )


def add_product():
    connection = connect_database()
    cursor = connection.cursor()

    product_id = int(input("Enter Product ID: "))
    name = input("Enter Product Name: ")
    price = float(input("Enter Product Price: "))
    quantity = int(input("Enter Quantity: "))

    query = """
        INSERT INTO products
        (product_id, product_name, price, quantity)
        VALUES (%s, %s, %s, %s)
    """

    values = (product_id, name, price, quantity)

    try:
        cursor.execute(query, values)
        connection.commit()
        print("Product added successfully.")

    except mysql.connector.Error as error:
        print(f"Error: {error}")

    finally:
        cursor.close()
        connection.close()


def view_products():
    connection = connect_database()
    cursor = connection.cursor()

    query = "SELECT * FROM products"

    try:
        cursor.execute(query)

        products = cursor.fetchall()

        print("\n--- Product List ---")

        for product in products:
            print(
                f"ID: {product[0]}, "
                f"Name: {product[1]}, "
                f"Price: {product[2]}, "
                f"Quantity: {product[3]}"
            )

    except mysql.connector.Error as error:
        print(f"Error: {error}")

    finally:
        cursor.close()
        connection.close()


def update_product():
    connection = connect_database()
    cursor = connection.cursor()

    product_id = int(input("Enter Product ID to update: "))
    price = float(input("Enter New Price: "))
    quantity = int(input("Enter New Quantity: "))

    query = """
        UPDATE products
        SET price = %s, quantity = %s
        WHERE product_id = %s
    """

    values = (price, quantity, product_id)

    try:
        cursor.execute(query, values)
        connection.commit()

        if cursor.rowcount > 0:
            print("Product updated successfully.")
        else:
            print("Product not found.")

    except mysql.connector.Error as error:
        print(f"Error: {error}")

    finally:
        cursor.close()
        connection.close()


def delete_product():
    connection = connect_database()
    cursor = connection.cursor()

    product_id = int(input("Enter Product ID to delete: "))

    query = "DELETE FROM products WHERE product_id = %s"

    try:
        cursor.execute(query, (product_id,))
        connection.commit()

        if cursor.rowcount > 0:
            print("Product deleted successfully.")
        else:
            print("Product not found.")

    except mysql.connector.Error as error:
        print(f"Error: {error}")

    finally:
        cursor.close()
        connection.close()


def main():
    while True:
        print("\n===== Product Management System =====")
        print("1. Add Product")
        print("2. View Products")
        print("3. Update Product")
        print("4. Delete Product")
        print("5. Exit")

        choice = input("Enter your choice: ")

        if choice == "1":
            add_product()
        elif choice == "2":
            view_products()
        elif choice == "3":
            update_product()
        elif choice == "4":
            delete_product()
        elif choice == "5":
            print("Thank you!")
            break
        else:
            print("Invalid choice.")


if __name__ == "__main__":
    main()