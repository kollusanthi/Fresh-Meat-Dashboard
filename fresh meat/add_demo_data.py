
import mysql.connector


def get_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="Sowji@54",
        database="freshmeat"
    )


def add_demo_data():

    email = input("Enter your registered seller email: ").strip().lower()

    connection = get_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        # Find seller
        cursor.execute("""
            SELECT id, shop_name
            FROM sellers
            WHERE email = %s
        """, (email,))

        seller = cursor.fetchone()

        if not seller:
            print("Seller account not found. Check your email.")
            return

        seller_id = seller["id"]

        # Prevent duplicate demo data
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS demo_seed_log (
                seller_id INT PRIMARY KEY
            ) ENGINE=InnoDB
        """)

        cursor.execute("""
            SELECT seller_id
            FROM demo_seed_log
            WHERE seller_id = %s
        """, (seller_id,))

        if cursor.fetchone():
            print("Demo data was already added for this seller.")
            print("No duplicate records were created.")
            return

        # 1. DEMO PRODUCTS
        products = [
            ("DEMO - Fresh Apples", "Fresh red apples", "Fruits", 180, 40),
            ("DEMO - Organic Tomatoes", "Farm fresh tomatoes", "Vegetables", 45, 50),
            ("DEMO - Fresh Milk", "One litre fresh milk", "Dairy", 60, 30),
            ("DEMO - Whole Wheat Bread", "Fresh bakery bread", "Bakery", 40, 25)
        ]

        product_ids = []

        for name, description, category, price, quantity in products:

            cursor.execute("""
                INSERT INTO products (
                    seller_id, name, description, category,
                    price, quantity, status
                )
                VALUES (%s, %s, %s, %s, %s, %s, 'Active')
            """, (
                seller_id, name, description,
                category, price, quantity
            ))

            product_ids.append(cursor.lastrowid)

        # 2. DEMO ORDERS AND ORDER ITEMS
        order_data = [
            {
                "name": "Demo Customer One",
                "phone": "9000000001",
                "address": "MVP Colony, Visakhapatnam",
                "status": "Pending",
                "items": [(0, 2), (1, 3)]
            },
            {
                "name": "Demo Customer Two",
                "phone": "9000000002",
                "address": "Gajuwaka, Visakhapatnam",
                "status": "Delivered",
                "items": [(2, 2)]
            },
            {
                "name": "Demo Customer Three",
                "phone": "9000000003",
                "address": "Madhurawada, Visakhapatnam",
                "status": "Pending",
                "items": [(3, 2)]
            }
        ]

        order_items = []

        for order in order_data:

            total = sum(
                products[index][3] * quantity
                for index, quantity in order["items"]
            )

            cursor.execute("""
                INSERT INTO orders (
                    customer_name, customer_phone,
                    customer_address, total_amount, order_status
                )
                VALUES (%s, %s, %s, %s, %s)
            """, (
                order["name"],
                order["phone"],
                order["address"],
                total,
                order["status"]
            ))

            order_id = cursor.lastrowid

            for index, quantity in order["items"]:

                product_id = product_ids[index]
                price = products[index][3]

                cursor.execute("""
                    INSERT INTO order_items (
                        order_id, product_id, seller_id,
                        quantity, price
                    )
                    VALUES (%s, %s, %s, %s, %s)
                """, (
                    order_id, product_id,
                    seller_id, quantity, price
                ))

                order_items.append({
                    "order_id": order_id,
                    "order_item_id": cursor.lastrowid,
                    "product_id": product_id,
                    "quantity": quantity,
                    "index": index
                })

                cursor.execute("""
                    UPDATE products
                    SET quantity = quantity - %s
                    WHERE id = %s
                """, (quantity, product_id))

        # 3. DEMO CUSTOMER RETURNS
        first_item = order_items[0]
        second_item = order_items[2]

        cursor.execute("""
            INSERT INTO return_requests (
                order_id, order_item_id, product_id, seller_id,
                customer_name, customer_phone, customer_address,
                quantity, reason, status
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'Requested')
        """, (
            first_item["order_id"],
            first_item["order_item_id"],
            first_item["product_id"],
            seller_id,
            "Demo Customer One",
            "9000000001",
            "MVP Colony, Visakhapatnam",
            1,
            "Product quality issue"
        ))

        cursor.execute("""
            INSERT INTO return_requests (
                order_id, order_item_id, product_id, seller_id,
                customer_name, customer_phone, customer_address,
                quantity, reason, status, seller_note,
                rider_name, rider_phone, rider_status
            )
            VALUES (
                %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s
            )
        """, (
            second_item["order_id"],
            second_item["order_item_id"],
            second_item["product_id"],
            seller_id,
            "Demo Customer Two",
            "9000000002",
            "Gajuwaka, Visakhapatnam",
            1,
            "Damaged packaging",
            "Pickup Assigned",
            "Return approved for pickup",
            "Demo Rider",
            "9888888888",
            "Assigned"
        ))

        # 4. DEMO CUSTOMER REVIEWS
        review_items = [order_items[1], order_items[3]]

        review_data = [
            (5, "Excellent quality. Very fresh product!"),
            (4, "Good product and timely delivery.")
        ]

        for item, (rating, comment) in zip(review_items, review_data):

            cursor.execute("""
                SELECT customer_name
                FROM orders
                WHERE id = %s
            """, (item["order_id"],))

            customer = cursor.fetchone()

            cursor.execute("""
                INSERT INTO reviews (
                    order_id, product_id, seller_id,
                    customer_name, rating, comment
                )
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                item["order_id"],
                item["product_id"],
                seller_id,
                customer["customer_name"],
                rating,
                comment
            ))

        # 5. DEMO NOTIFICATIONS
        notifications = [
            ("New demo order", "You received a demo customer order."),
            ("Return request received", "A demo customer requested a product return."),
            ("Customer review received", "A demo customer submitted a 5-star review."),
            ("Product stock update", "Demo product quantities have been updated.")
        ]

        for title, message in notifications:

            cursor.execute("""
                INSERT INTO notifications (
                    seller_id, title, message, is_read
                )
                VALUES (%s, %s, %s, 0)
            """, (seller_id, title, message))

        # Record demo data insertion
        cursor.execute("""
            INSERT INTO demo_seed_log (seller_id)
            VALUES (%s)
        """, (seller_id,))

        connection.commit()

        print("\nDemo data added successfully!")
        print("Products: 4")
        print("Orders: 3")
        print("Customer Returns: 2")
        print("Customer Reviews: 2")
        print("Notifications: 4")
        print("Seller:", seller["shop_name"])

    except Exception as error:
        connection.rollback()
        print("Error adding demo data:", error)

    finally:
        cursor.close()
        connection.close()


if __name__ == "__main__":
    add_demo_data()
