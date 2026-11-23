
from database import get_db_connection

conn = get_db_connection()

customer = conn.execute(
    "SELECT id FROM customers WHERE email = ?",
    ("customer@example.com",)
).fetchone()

if customer:
    print("Sample customer already exists!")
else:
    conn.execute("""
        INSERT INTO customers (name, email, phone, status)
        VALUES (?, ?, ?, ?)
    """, (
        "Priya Sharma",
        "customer@example.com",
        "9876543212",
        "Active"
    ))

    conn.commit()
    print("Sample customer added successfully!")

conn.close()
