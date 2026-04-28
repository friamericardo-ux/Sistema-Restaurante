# 005_fix_delivery_and_mesas_v2.py
# Correção de esquema para Delivery e Mesas usando Python.

def upgrade(cursor, conn):
    def column_exists(table, column):
        try:
            cursor.execute(f"SHOW COLUMNS FROM {table} LIKE '{column}'")
            return cursor.fetchone() is not None
        except:
            return False

    # 1. PEDIDOS_DELIVERY
    cols_delivery = [
        ('cliente_endereco', 'TEXT AFTER cliente_telefone'),
        ('itens', 'TEXT AFTER cliente_endereco'),
        ('taxa_entrega', 'DOUBLE DEFAULT 5.0 AFTER itens'),
        ('forma_pagamento', "VARCHAR(50) DEFAULT '' AFTER total"),
        ('troco', 'DOUBLE DEFAULT 0 AFTER forma_pagamento')
    ]
    for col, spec in cols_delivery:
        if not column_exists('pedidos_delivery', col):
            cursor.execute(f"ALTER TABLE pedidos_delivery ADD COLUMN {col} {spec}")

    # 2. MESAS
    if not column_exists('mesas', 'total'):
        cursor.execute("ALTER TABLE mesas ADD COLUMN total DOUBLE DEFAULT 0 AFTER numero")

    # 3. ITENS
    cols_itens = [
        ('nome', 'VARCHAR(255) AFTER mesa_id'),
        ('preco', 'DOUBLE AFTER nome'),
        ('observacao', "VARCHAR(500) DEFAULT '' AFTER quantidade")
    ]
    for col, spec in cols_itens:
        if not column_exists('itens', col):
            cursor.execute(f"ALTER TABLE itens ADD COLUMN {col} {spec}")

    # 4. RESTAURANTE_ID (Redundância Multi-tenancy)
    tabelas = ['pedidos_delivery', 'mesas', 'itens']
    for tabela in tabelas:
        if not column_exists(tabela, 'restaurante_id'):
            cursor.execute(f"ALTER TABLE {tabela} ADD COLUMN restaurante_id INT DEFAULT 1")
    
    print("[migration 005] Tabelas de Delivery e Mesas corrigidas via Python.")
