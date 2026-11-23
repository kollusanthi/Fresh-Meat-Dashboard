
from database import get_db_connection

conn = get_db_connection()

rider = conn.execute(
    "SELECT id FROM riders WHERE email = ?",
    ("rider@example.com",)
).fetchone()

if rider:
    print("Sample rider already exists!")
else:
    conn.execute("""
        INSERT INTO riders (name, email, phone, status)
        VALUES (?, ?, ?, ?)
    """, (
        "Arjun Kumar",
        "rider@example.com",
        "9876543211",
        "Pending"
    ))

    conn.commit()
    print("Sample rider added successfully!")

conn.close()
