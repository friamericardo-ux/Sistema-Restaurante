# 010_fix_adicional_categoria_schema.py
# Corrige o schema da tabela adicional_categoria que foi criada
# incorretamente pelo criar_tabela.py com coluna 'nome' extra.
# A coluna 'nome' não existe no schema oficial (db.py) e quebra
# o INSERT em adicionar_adicional() com erro:
#   Field 'nome' doesn't have a default value

def upgrade(cursor, conn):
    def column_exists(table, column):
        try:
            cursor.execute(f"SHOW COLUMNS FROM {table} LIKE '{column}'")
            return cursor.fetchone() is not None
        except:
            return False

    if column_exists('adicional_categoria', 'nome'):
        cursor.execute("ALTER TABLE adicional_categoria DROP COLUMN nome")
        print("[migration 010] Coluna 'nome' removida de adicional_categoria")

    print("[migration 010] Schema de adicional_categoria sincronizado.")
