# 013_fix_configuracoes_unique.py
# Remove UNIQUE KEY antiga em (chave) que quebrava isolamento multi-tenant.
# ON DUPLICATE KEY UPDATE usava essa UNIQUE em vez da PK composta,
# fazendo set_config() gravar sempre em restaurante_id=1.
#
# Seguro para rodar em producao: idempotente, nao perde dados.

def upgrade(cursor, conn):
    # 1. Remove UNIQUE KEY obsoleta em (chave) — MySQL
    try:
        cursor.execute("SELECT 1 FROM information_schema.TABLE_CONSTRAINTS "
                       "WHERE CONSTRAINT_SCHEMA = DATABASE() "
                       "AND TABLE_NAME = 'configuracoes' "
                       "AND CONSTRAINT_NAME = 'chave'")
        if cursor.fetchone():
            cursor.execute("DROP INDEX chave ON configuracoes")
            print("[migration 013] UNIQUE KEY 'chave' removida")
    except Exception:
        pass  # SQLite ou index ja nao existe

    # 2. Garante UNIQUE composta (chave, restaurante_id) — MySQL
    try:
        cursor.execute("SELECT 1 FROM information_schema.TABLE_CONSTRAINTS "
                       "WHERE CONSTRAINT_SCHEMA = DATABASE() "
                       "AND TABLE_NAME = 'configuracoes' "
                       "AND CONSTRAINT_NAME = 'chave_restaurante'")
        if not cursor.fetchone():
            cursor.execute(
                "CREATE UNIQUE INDEX chave_restaurante "
                "ON configuracoes (chave, restaurante_id)"
            )
            print("[migration 013] UNIQUE KEY 'chave_restaurante' criada")
    except Exception:
        pass  # SQLite — nao precisa, PK ja garante unicidade

    conn.commit()
