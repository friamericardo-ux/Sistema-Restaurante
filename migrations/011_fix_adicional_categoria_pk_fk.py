# 011_fix_adicional_categoria_pk_fk.py
# Corrige PK e FK da tabela adicional_categoria:
#   Antes:  PK = id (surrogate), sem FK
#   Depois: PK = (adicional_id, categoria), FK → adicionais(id) ON DELETE CASCADE
#
# Esta migration é IDEMPOTENTE: só executa se a PK ainda for 'id'.
# Segura para produção: preserva dados, limpa orphans/duplicatas primeiro.

def upgrade(cursor, conn):
    def column_exists(table, column):
        try:
            cursor.execute(f"SHOW COLUMNS FROM {table} LIKE '{column}'")
            return cursor.fetchone() is not None
        except:
            return False

    def pk_is_id():
        """Retorna True se a PK atual for a coluna 'id' (surrogate legada)."""
        try:
            cursor.execute("SHOW INDEX FROM adicional_categoria WHERE Key_name = 'PRIMARY'")
            pk_cols = [row[4] for row in cursor.fetchall()]  # Column_name is at index 4
            return pk_cols == ['id']
        except:
            return False

    # ── Só executa se a PK ainda é a surrogate 'id' ──
    if not pk_is_id():
        print("[migration 011] PK já está corrigida. Nada a fazer.")
        return

    print("[migration 011] Corrigindo PK e FK de adicional_categoria...")

    # ── 1. Limpar registros com NULL (resquício do schema legado id+nome) ──
    cursor.execute("DELETE FROM adicional_categoria WHERE adicional_id IS NULL OR categoria IS NULL OR categoria = ''")
    print(f"[migration 011] Linhas com NULL removidas: {cursor.rowcount}")

    # ── 2. Remover duplicatas de (adicional_id, categoria) ──
    #    Mantém a linha com maior id, remove as demais
    cursor.execute("""
        DELETE t1 FROM adicional_categoria t1
        INNER JOIN adicional_categoria t2
        WHERE t1.id < t2.id
        AND t1.adicional_id = t2.adicional_id
        AND t1.categoria = t2.categoria
    """)
    print(f"[migration 011] Duplicatas removidas: {cursor.rowcount}")

    # ── 3. Remover órfãos (adicional_id que não existe em adicionais) ──
    cursor.execute("""
        DELETE ac FROM adicional_categoria ac
        LEFT JOIN adicionais a ON a.id = ac.adicional_id
        WHERE a.id IS NULL
    """)
    print(f"[migration 011] Órfãos removidos: {cursor.rowcount}")

    conn.commit()

    # ── 4. Remover AUTO_INCREMENT da coluna id ──
    cursor.execute("ALTER TABLE adicional_categoria MODIFY id INT NOT NULL")
    print("[migration 011] AUTO_INCREMENT removido de id")

    # ── 5. Drop da PK antiga (id) ──
    cursor.execute("ALTER TABLE adicional_categoria DROP PRIMARY KEY")
    print("[migration 011] PK antiga (id) removida")

    # ── 6. Drop da coluna id ──
    cursor.execute("ALTER TABLE adicional_categoria DROP COLUMN id")
    print("[migration 011] Coluna id removida")

    # ── 7. NOT NULL nas colunas da nova PK ──
    cursor.execute("ALTER TABLE adicional_categoria MODIFY adicional_id INT NOT NULL")
    cursor.execute("ALTER TABLE adicional_categoria MODIFY categoria VARCHAR(100) NOT NULL")
    print("[migration 011] Colunas adicional_id e categoria agora são NOT NULL")

    # ── 8. Nova PK composta ──
    cursor.execute("ALTER TABLE adicional_categoria ADD PRIMARY KEY (adicional_id, categoria)")
    print("[migration 011] Nova PK composta (adicional_id, categoria) adicionada")

    # ── 9. FK para adicionais(id) com ON DELETE CASCADE ──
    cursor.execute("""
        ALTER TABLE adicional_categoria
        ADD CONSTRAINT fk_adicional_categoria_adicional
        FOREIGN KEY (adicional_id) REFERENCES adicionais(id)
        ON DELETE CASCADE
    """)
    print("[migration 011] FK adicional_id → adicionais(id) ON DELETE CASCADE adicionada")

    conn.commit()
    print("[migration 011] PK e FK de adicional_categoria corrigidas com sucesso.")
