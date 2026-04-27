import pymysql
from urllib.parse import urlparse
import os

db_url = "mysql://root:@localhost/comanda_digital"
parsed = urlparse(db_url)

try:
    conn = pymysql.connect(
        host=parsed.hostname or 'localhost',
        port=parsed.port or 3306,
        user=parsed.username or 'root',
        password=parsed.password or '',
        database=parsed.path.lstrip('/'),
        charset='utf8mb4'
    )
    cursor = conn.cursor()
    
    print("--- TABLES ---")
    cursor.execute("SHOW TABLES")
    tables = [t[0] for t in cursor.fetchall()]
    for t in tables:
        print(f"\nTable: {t}")
        cursor.execute(f"DESCRIBE {t}")
        for col in cursor.fetchall():
            print(f"  {col[0]}: {col[1]}")
            
    conn.close()
except Exception as e:
    print(f"Error: {e}")
