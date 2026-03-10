import sqlite3
from config import Config

conn = sqlite3.connect(Config.DB_PATH)
cursor = conn.cursor()
cursor.execute("ALTER TABLE produtos ADD COLUMN foto TEXT DEFAULT NULL")
conn.commit()
conn.close()
print("Coluna foto adicionada com sucesso!")