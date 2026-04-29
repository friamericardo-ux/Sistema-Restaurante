# 008_status_mesas.py
# Adiciona coluna status ENUM('livre','aberta','ocupada','conta_pedida') na tabela mesas

def upgrade(cursor, conn):
    def column_exists(table, column):
        try:
            cursor.execute(f"SHOW COLUMNS FROM {table} LIKE '{column}'")
            return cursor.fetchone() is not None
        except:
            return False

    tabela = 'mesas'

    if not column_exists(tabela, 'status'):
        cursor.execute(f"ALTER TABLE {tabela} ADD COLUMN status ENUM('livre','aberta','ocupada','conta_pedida') DEFAULT 'livre'")
        print("[migration 008] Coluna 'status' adicionada a mesas")

    print("[migration 008] Status das mesas configurado.")