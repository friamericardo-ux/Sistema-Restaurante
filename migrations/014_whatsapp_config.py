# 014_whatsapp_config.py
# Creates dedicated whatsapp_config table per tenant.
# Migrates existing config values from configuracoes key-value table.

def upgrade(cursor, conn):
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS whatsapp_config (
            id INT PRIMARY KEY AUTO_INCREMENT,
            restaurante_id INT NOT NULL UNIQUE,
            instance_name VARCHAR(100) DEFAULT 'pantanal-burger',
            webhook_url VARCHAR(255) DEFAULT '',
            enabled TINYINT DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)

    # Migrate existing instance_name from configuracoes if any
    cursor.execute("""
        INSERT INTO whatsapp_config (restaurante_id, instance_name, enabled)
        SELECT c.restaurante_id,
               COALESCE(c.valor, 'pantanal-burger') AS instance_name,
               0 AS enabled
        FROM configuracoes c
        WHERE c.chave = 'evolution_instance_name'
        ON DUPLICATE KEY UPDATE instance_name = VALUES(instance_name)
    """)

    conn.commit()
