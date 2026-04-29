# 009_add_ativo_users.py
# Adiciona coluna ativo na tabela users para permitir desativação sem delete

def upgrade(cursor, conn):
    def column_exists(table, column):
        try:
            cursor.execute(f"SHOW COLUMNS FROM {table} LIKE '{column}'")
            return cursor.fetchone() is not None
        except:
            return False

    tabela = 'users'

    if not column_exists(tabela, 'ativo'):
        cursor.execute(f"ALTER TABLE {tabela} ADD COLUMN ativo TINYINT DEFAULT 1")
        print("[migration 009] Coluna 'ativo' adicionada a users")

    print("[migration 009] Coluna ativo em users configurada.")