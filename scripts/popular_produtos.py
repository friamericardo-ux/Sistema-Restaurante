
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sqlite3
from config import Config

def popular_produtos():
    conn = sqlite3.connect(Config.Config.DB_PATH)
    cursor = conn.cursor()
    
    # Lista de produtos exemplo
    produtos = [
        ("X-Burguer", 18.50),
        ("X-Bacon", 22.00),
        ("X-Salada", 20.00),
        ("Fritas P", 8.00),
        ("Fritas G", 12.00),
        ("Refrigerante", 6.00),
        ("Suco Natural", 9.00),
        ("Água", 3.50),
        ("Sorvete", 10.00),
        ("Coca-Cola 600ml", 7.00),
    ]
    
    cursor.executemany("""
        INSERT OR IGNORE INTO itens (nome, preco)
        VALUES (?, ?)
    """, produtos)
    
    conn.commit()
    print(f"✅ {cursor.rowcount} produtos cadastrados com sucesso!")
    
    conn.close()

if __name__ == "__main__":
    popular_produtos()