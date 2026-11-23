from database import get_db_connection

conn = get_db_connection()

customer = conn.execute(
    "SELECT id FROM customers LIMIT 1"
).fetchone()

if customer:
    conn.execute("""
        INSERT INTO orders (customer_id, total_amount, status)
        VALUES (?, ?, ?)
    """, (customer["id"], 500, "Pending"))

    conn.commit()
    print("Sample order added successfully!")
else:
    print("No customer found!")

conn.close()