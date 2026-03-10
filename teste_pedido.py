# testar_pedido.py
from data.db import get_connection
import json
import sqlite3

db = get_connection()
db.row_factory = sqlite3.Row
cursor = db.cursor()

cursor.execute("SELECT id, cliente_nome, itens, total FROM pedidos_delivery ORDER BY id DESC LIMIT 1")
pedido = cursor.fetchone()

if pedido:
    print(f"\n=== PEDIDO #{pedido['id']} ===")
    print(f"Cliente: {pedido['cliente_nome']}")
    print(f"Total: R$ {pedido['total']:.2f}")
    print(f"\nITENS SALVOS:")
    itens = json.loads(pedido['itens'])
    for item in itens:
        print(f"  - {item.get('nome')} x{item.get('quantidade')} = R$ {item.get('preco'):.2f}")
else:
    print("Nenhum pedido encontrado!")

db.close()
input("\nPressione Enter para sair...")