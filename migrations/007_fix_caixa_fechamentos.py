# 007_fix_caixa_fechamentos.py
# Garante que a tabela caixa_fechamentos tenha as colunas necessárias para o resumo.

def upgrade(cursor, conn):
    def column_exists(table, column):
        try:
            cursor.execute(f"SHOW COLUMNS FROM {table} LIKE '{column}'")
            return cursor.fetchone() is not None
        except:
            return False

    tabela = 'caixa_fechamentos'
    
    # 1. fechado_em (TIMESTAMP)
    if not column_exists(tabela, 'fechado_em'):
        cursor.execute(f"ALTER TABLE {tabela} ADD COLUMN fechado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
        print(f"[migration 007] Coluna 'fechado_em' adicionada a {tabela}")

    # 2. data (VARCHAR 10)
    if not column_exists(tabela, 'data'):
        cursor.execute(f"ALTER TABLE {tabela} ADD COLUMN data VARCHAR(10) AFTER id")
        print(f"[migration 007] Coluna 'data' adicionada a {tabela}")

    # 3. restaurante_id (INT)
    if not column_exists(tabela, 'restaurante_id'):
        cursor.execute(f"ALTER TABLE {tabela} ADD COLUMN restaurante_id INT DEFAULT 1")
        print(f"[migration 007] Coluna 'restaurante_id' adicionada a {tabela}")

    print("[migration 007] Sincronização de caixa_fechamentos concluída.")
