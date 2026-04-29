from data.db import get_connection, is_mysql

conn = get_connection()
cursor = conn.cursor()

if is_mysql():
    cursor.execute("DESCRIBE mesas")
    for row in cursor.fetchall():
        print(row)
else:
    cursor.execute("PRAGMA table_info(mesas)")
    for row in cursor.fetchall():
        print(row)

conn.close()
