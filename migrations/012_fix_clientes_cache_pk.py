# 012_fix_clientes_cache_pk.py
# Corrige chave primaria de clientes_cache para (telefone, restaurante_id)
# garantindo isolamento multi-tenant — IDOR corrigido na Tarefa 1.1
#
# Seguro para rodar em producao: idempotente, nao perde dados.
# MySQL: ALTER TABLE DROP/ADD PRIMARY KEY
# SQLite: recria tabela com PK composta

def _is_mysql(cursor):
    """Detecta se o banco e MySQL tentando comando exclusivo."""
    try:
        cursor.execute("SHOW COLUMNS FROM clientes_cache LIKE 'telefone'")
        cursor.fetchone()
        return True
    except Exception:
        return False


def _pk_ja_composta_mysql(cursor):
    cursor.execute("""
        SELECT GROUP_CONCAT(COLUMN_NAME ORDER BY ORDINAL_POSITION)
        FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = 'clientes_cache'
          AND CONSTRAINT_NAME = 'PRIMARY'
    """)
    row = cursor.fetchone()
    pk_columns = row[0] if row and row[0] else ''
    return 'restaurante_id' in pk_columns


def _pk_ja_composta_sqlite(cursor):
    cursor.execute("PRAGMA table_info(clientes_cache)")
    columns = cursor.fetchall()
    # col[5] > 0 indica que a coluna faz parte da PK
    pk_cols = [col[1] for col in columns if col[5] > 0]
    return 'restaurante_id' in pk_cols


def _upgrade_mysql(cursor, conn):
    # 1. Garante que restaurante_id existe (migration 006 pode nao ter rodado)
    try:
        cursor.execute("SELECT restaurante_id FROM clientes_cache LIMIT 1")
    except Exception:
        cursor.execute(
            "ALTER TABLE clientes_cache ADD COLUMN restaurante_id INT NOT NULL DEFAULT 1"
        )

    # 2. Verifica se PK ja inclui restaurante_id
    if _pk_ja_composta_mysql(cursor):
        print("[migration 012] PK de clientes_cache ja e composta — nada a fazer")
        return

    # 3. Drop PK antiga (telefone) e cria composta (telefone, restaurante_id)
    cursor.execute("ALTER TABLE clientes_cache DROP PRIMARY KEY")
    cursor.execute(
        "ALTER TABLE clientes_cache ADD PRIMARY KEY (telefone, restaurante_id)"
    )
    conn.commit()
    print("[migration 012] PK de clientes_cache alterada para (telefone, restaurante_id) [MySQL]")


def _upgrade_sqlite(cursor, conn):
    # 1. Garante que restaurante_id existe
    try:
        cursor.execute("SELECT restaurante_id FROM clientes_cache LIMIT 1")
    except Exception:
        cursor.execute(
            "ALTER TABLE clientes_cache ADD COLUMN restaurante_id INTEGER NOT NULL DEFAULT 1"
        )

    # 2. Verifica se PK ja inclui restaurante_id
    if _pk_ja_composta_sqlite(cursor):
        print("[migration 012] PK de clientes_cache ja e composta — nada a fazer")
        return

    # 3. SQLite nao suporta ALTER PRIMARY KEY — recriamos a tabela
    cursor.execute("""
        CREATE TABLE clientes_cache_new (
            telefone TEXT NOT NULL,
            nome TEXT,
            endereco TEXT,
            atualizado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            restaurante_id INTEGER NOT NULL DEFAULT 1,
            PRIMARY KEY (telefone, restaurante_id)
        )
    """)

    # Copia dados (COALESCE para restaurante_id caso nulo)
    cursor.execute("""
        INSERT INTO clientes_cache_new (telefone, nome, endereco, atualizado_em, restaurante_id)
        SELECT telefone, nome, endereco, atualizado_em, COALESCE(restaurante_id, 1)
        FROM clientes_cache
    """)

    cursor.execute("DROP TABLE clientes_cache")
    cursor.execute("ALTER TABLE clientes_cache_new RENAME TO clientes_cache")
    conn.commit()
    print("[migration 012] PK de clientes_cache alterada para (telefone, restaurante_id) [SQLite]")


def upgrade(cursor, conn):
    if _is_mysql(cursor):
        _upgrade_mysql(cursor, conn)
    else:
        _upgrade_sqlite(cursor, conn)
