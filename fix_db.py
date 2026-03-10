import sqlite3

conn = sqlite3.connect('data/database.db')
cursor = conn.cursor()

try:
    cursor.execute("ALTER TABLE pedidos_delivery ADD COLUMN status TEXT DEFAULT 'novo'")
    conn.commit()
    print("Coluna adicionada com sucesso!")
except Exception as e:
    print(f"Resultado: {e}")

conn.close()