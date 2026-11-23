from database import get_db_connection

conn = get_db_connection()

order = conn.execute(
    "SELECT id FROM orders ORDER BY id DESC LIMIT 1"
).fetchone()

if order:
    conn.execute("""
        INSERT INTO payments (order_id, amount, payment_status)
        VALUES (?, ?, ?)
    """, (order["id"], 500, "Pending"))

    conn.commit()
    print("Sample payment added successfully!")
else:
    print("No order found!")

conn.close()