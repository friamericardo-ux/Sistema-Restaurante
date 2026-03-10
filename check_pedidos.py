import sqlite3

conn = sqlite3.connect('data/database.db')
cursor = conn.cursor()

cursor.execute("SELECT id, cliente_nome, status FROM pedidos_delivery")
pedidos = cursor.fetchall()

for p in pedidos:
    print(p)

conn.close()