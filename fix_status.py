import sqlite3

conn = sqlite3.connect('data/database.db')
cursor = conn.cursor()

cursor.execute("UPDATE pedidos_delivery SET status = 'novo' WHERE status = 'pendente'")
conn.commit()
print(f"Pedidos atualizados: {cursor.rowcount}")
conn.close()