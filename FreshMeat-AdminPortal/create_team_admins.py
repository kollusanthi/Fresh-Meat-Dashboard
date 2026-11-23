from database import get_db_connection

conn = get_db_connection()

conn.execute("DELETE FROM admins WHERE id != 1")

conn.commit()
conn.close()

print("Extra accounts deleted successfully!")