import sqlite3
conn = sqlite3.connect('database.db')
cursor = conn.cursor()
cursor.execute("SELECT * FROM produtos")
dados = cursor.fetchall()
for produto in dados:
    print("\n--- PRODUTO ---")
    for i, valor in enumerate(produto):
        print(f"  Índice {i}: {valor}")
conn.close()