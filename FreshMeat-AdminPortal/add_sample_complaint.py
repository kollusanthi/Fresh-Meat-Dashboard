from database import get_db_connection

conn = get_db_connection()

customer = conn.execute(
    "SELECT id FROM customers LIMIT 1"
).fetchone()

if customer:
    conn.execute("""
        INSERT INTO complaints
        (customer_id, subject, message, status)
        VALUES (?, ?, ?, ?)
    """, (
        customer["id"],
        "Late Delivery",
        "My order was delivered late.",
        "Open"
    ))

    conn.commit()
    print("Sample complaint added successfully!")
else:
    print("No customer found!")

conn.close()