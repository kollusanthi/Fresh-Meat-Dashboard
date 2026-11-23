
from database import get_db_connection, init_db

init_db()

conn = get_db_connection()

username = "admin"
password = "Admin@123"

existing = conn.execute(
    "SELECT id FROM admins WHERE username = ?",
    (username,)
).fetchone()

if existing:
    print("Admin account already exists!")
else:
    conn.execute(
        "INSERT INTO admins (username, password) VALUES (?, ?)",
        (username, password)
    )
    conn.commit()
    print("Admin account created successfully!")

conn.close()
