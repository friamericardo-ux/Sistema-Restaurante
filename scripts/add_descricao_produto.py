"""
Migração segura: adiciona coluna 'descricao' na tabela produtos.
Pode ser executado múltiplas vezes — ignora se a coluna já existir.
"""
import sqlite3
import os, sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from config import Config

conn = sqlite3.connect(Config.DB_PATH)
cursor = conn.cursor()

try:
    cursor.execute("ALTER TABLE produtos ADD COLUMN descricao TEXT DEFAULT ''")
    conn.commit()
    print("✅ Coluna 'descricao' adicionada com sucesso!")
except sqlite3.OperationalError as e:
    if "duplicate column name" in str(e):
        print("ℹ️  Coluna 'descricao' já existe — nenhuma alteração feita.")
    else:
        raise
finally:
    conn.close()
