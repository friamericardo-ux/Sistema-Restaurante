-- 006_complete_schema_sync.sql
-- Sincronização abrangente do esquema com as expectativas do app.py e repository.py

-- 1. PRODUTOS: Adição de colunas emoji e foto
ALTER TABLE produtos ADD COLUMN IF NOT EXISTS emoji VARCHAR(10) DEFAULT '🍽️' AFTER categoria;
ALTER TABLE produtos ADD COLUMN IF NOT EXISTS foto VARCHAR(255) DEFAULT NULL AFTER emoji;

-- Migração de dados de imagem para foto (caso imagem exista)
-- Nota: MySQL 8 ignora erro se a coluna imagem não existir no dialeto da migration.py
UPDATE produtos SET foto = imagem WHERE foto IS NULL;

-- 2. ADICIONAIS: Coluna ativo
ALTER TABLE adicionais ADD COLUMN IF NOT EXISTS ativo TINYINT DEFAULT 1;

-- 3. ADICIONAL_CATEGORIA: Ajustes de colunas
ALTER TABLE adicional_categoria ADD COLUMN IF NOT EXISTS adicional_id INT;
ALTER TABLE adicional_categoria ADD COLUMN IF NOT EXISTS categoria VARCHAR(100);

-- 4. USERS: Licença e Tenant
ALTER TABLE users ADD COLUMN IF NOT EXISTS licenca_vencimento DATE DEFAULT NULL;
ALTER TABLE users ADD COLUMN IF NOT EXISTS restaurante_id INT DEFAULT 1;

-- 5. CONFIGURACOES: Timestamp de atualização
ALTER TABLE configuracoes ADD COLUMN IF NOT EXISTS atualizado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP;

-- 6. FECHAMENTOS_CAIXA: Ajuste de campos de relatório
ALTER TABLE fechamentos_caixa ADD COLUMN IF NOT EXISTS data VARCHAR(10) AFTER id;
ALTER TABLE fechamentos_caixa ADD COLUMN IF NOT EXISTS total_faturado DOUBLE DEFAULT 0 AFTER data;
ALTER TABLE fechamentos_caixa ADD COLUMN IF NOT EXISTS total_pedidos INT DEFAULT 0 AFTER total_faturado;
ALTER TABLE fechamentos_caixa ADD COLUMN IF NOT EXISTS total_entregas INT DEFAULT 0 AFTER total_pedidos;
ALTER TABLE fechamentos_caixa ADD COLUMN IF NOT EXISTS valor_entregas DOUBLE DEFAULT 0 AFTER total_entregas;

-- 7. REFORÇO MULTI-TENANCY: Garantir restaurante_id em todas as tabelas
ALTER TABLE produtos ADD COLUMN IF NOT EXISTS restaurante_id INT DEFAULT 1;
ALTER TABLE adicionais ADD COLUMN IF NOT EXISTS restaurante_id INT DEFAULT 1;
ALTER TABLE adicional_categoria ADD COLUMN IF NOT EXISTS restaurante_id INT DEFAULT 1;
ALTER TABLE historico_mesas ADD COLUMN IF NOT EXISTS restaurante_id INT DEFAULT 1;
ALTER TABLE caixa_fechamentos ADD COLUMN IF NOT EXISTS restaurante_id INT DEFAULT 1;
ALTER TABLE fechamentos_caixa ADD COLUMN IF NOT EXISTS restaurante_id INT DEFAULT 1;
ALTER TABLE caixa_sessoes ADD COLUMN IF NOT EXISTS restaurante_id INT DEFAULT 1;
ALTER TABLE clientes_cache ADD COLUMN IF NOT EXISTS restaurante_id INT DEFAULT 1;
ALTER TABLE configuracoes ADD COLUMN IF NOT EXISTS restaurante_id INT DEFAULT 1;
