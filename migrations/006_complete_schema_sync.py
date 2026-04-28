# 006_complete_schema_sync.py
# Sincronização abrangente do esquema usando Python para compatibilidade entre versões do MySQL.

def upgrade(cursor, conn):
    def column_exists(table, column):
        try:
            cursor.execute(f"SHOW COLUMNS FROM {table} LIKE '{column}'")
            return cursor.fetchone() is not None
        except:
            return False

    # 1. PRODUTOS: emoji e foto
    if not column_exists('produtos', 'emoji'):
        cursor.execute("ALTER TABLE produtos ADD COLUMN emoji VARCHAR(10) DEFAULT '🍽️' AFTER categoria")
    
    if not column_exists('produtos', 'foto'):
        cursor.execute("ALTER TABLE produtos ADD COLUMN foto VARCHAR(255) DEFAULT NULL AFTER emoji")
    
    # Tenta migrar dados de imagem para foto se imagem existir
    try:
        cursor.execute("UPDATE produtos SET foto = imagem WHERE foto IS NULL")
    except:
        pass

    # 2. ADICIONAIS: coluna ativo
    if not column_exists('adicionais', 'ativo'):
        cursor.execute("ALTER TABLE adicionais ADD COLUMN ativo TINYINT DEFAULT 1")

    # 3. ADICIONAL_CATEGORIA: Reestruturação
    if not column_exists('adicional_categoria', 'adicional_id'):
        cursor.execute("ALTER TABLE adicional_categoria ADD COLUMN adicional_id INT")
    
    if not column_exists('adicional_categoria', 'categoria'):
        cursor.execute("ALTER TABLE adicional_categoria ADD COLUMN categoria VARCHAR(100)")

    # 4. USERS: licenca_vencimento e restaurante_id
    if not column_exists('users', 'licenca_vencimento'):
        cursor.execute("ALTER TABLE users ADD COLUMN licenca_vencimento DATE DEFAULT NULL")
    
    if not column_exists('users', 'restaurante_id'):
        cursor.execute("ALTER TABLE users ADD COLUMN restaurante_id INT DEFAULT 1")

    # 5. CONFIGURACOES: atualizado_em
    if not column_exists('configuracoes', 'atualizado_em'):
        cursor.execute("ALTER TABLE configuracoes ADD COLUMN atualizado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP")

    # 6. FECHAMENTOS_CAIXA (Ajuste para o padrão esperado no app.py)
    if not column_exists('fechamentos_caixa', 'data'):
        cursor.execute("ALTER TABLE fechamentos_caixa ADD COLUMN data VARCHAR(10) AFTER id")
    
    if not column_exists('fechamentos_caixa', 'total_faturado'):
        cursor.execute("ALTER TABLE fechamentos_caixa ADD COLUMN total_faturado DOUBLE DEFAULT 0 AFTER data")
    
    if not column_exists('fechamentos_caixa', 'total_pedidos'):
        cursor.execute("ALTER TABLE fechamentos_caixa ADD COLUMN total_pedidos INT DEFAULT 0 AFTER total_faturado")
    
    if not column_exists('fechamentos_caixa', 'total_entregas'):
        cursor.execute("ALTER TABLE fechamentos_caixa ADD COLUMN total_entregas INT DEFAULT 0 AFTER total_pedidos")
    
    if not column_exists('fechamentos_caixa', 'valor_entregas'):
        cursor.execute("ALTER TABLE fechamentos_caixa ADD COLUMN valor_entregas DOUBLE DEFAULT 0 AFTER total_entregas")

    # 7. Garantir restaurante_id em tabelas críticas (Redundância Multi-tenancy)
    tabelas_tenant = [
        'produtos', 'adicionais', 'adicional_categoria', 
        'historico_mesas', 'caixa_fechamentos', 'fechamentos_caixa',
        'caixa_sessoes', 'clientes_cache', 'configuracoes'
    ]
    
    for tabela in tabelas_tenant:
        if not column_exists(tabela, 'restaurante_id'):
            cursor.execute(f"ALTER TABLE {tabela} ADD COLUMN restaurante_id INT DEFAULT 1")
    
    print("[migration 006] Esquema sincronizado com sucesso via Python.")
