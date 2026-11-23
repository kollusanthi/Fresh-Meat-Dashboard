
from database import get_db_connection

conn = get_db_connection()

product = conn.execute(
    "SELECT id FROM products WHERE name = ?",
    ("Fresh Chicken",)
).fetchone()

if product:
    print("Sample product already exists!")
else:
    seller = conn.execute(
        "SELECT id FROM sellers WHERE status = 'Approved' LIMIT 1"
    ).fetchone()

    if seller:
        conn.execute("""
            INSERT INTO products (seller_id, name, category, price, status)
            VALUES (?, ?, ?, ?, ?)
        """, (seller["id"], "Fresh Chicken", "Chicken", 250, "Pending"))

        conn.commit()
        print("Sample product added successfully!")
    else:
        print("No approved seller found!")

conn.close()
