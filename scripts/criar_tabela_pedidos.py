import sys
import os

# Adiciona a pasta raiz ao caminho de busca do Python
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sqlite3
from config import Config

def criar_tabela_pedidos():
    conn = sqlite3.connect(Config.Config.DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pedidos_delivery (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cliente_nome TEXT NOT NULL,
            cliente_telefone TEXT NOT NULL,
            cliente_endereco TEXT NOT NULL,
            itens TEXT NOT NULL,
            taxa_entrega REAL DEFAULT 5.00,
            total REAL NOT NULL,
            status TEXT DEFAULT 'pendente',
            tempo_estimado TEXT DEFAULT '40 a 50 minutos',
            criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    conn.commit()
    conn.close()
    print("✅ Tabela 'pedidos_delivery' criada com sucesso!")

if __name__ == "__main__":
    criar_tabela_pedidos()