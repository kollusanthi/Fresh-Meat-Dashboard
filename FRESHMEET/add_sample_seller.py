
from database import get_db_connection

conn = get_db_connection()

seller = conn.execute(
    "SELECT id FROM sellers WHERE email = ?",
    ("seller@example.com",)
).fetchone()

if seller:
    print("Sample seller already exists!")
else:
    conn.execute("""
        INSERT INTO sellers (name, email, phone, status)
        VALUES (?, ?, ?, ?)
    """, (
        "Ravi Fresh Meat Store",
        "seller@example.com",
        "9876543210",
        "Pending"
    ))

    conn.commit()
    print("Sample seller added successfully!")

conn.close()
