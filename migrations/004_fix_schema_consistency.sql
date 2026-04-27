-- Adiciona colunas faltantes em caixa_fechamentos
ALTER TABLE caixa_fechamentos ADD COLUMN data DATE;
ALTER TABLE caixa_fechamentos ADD COLUMN total_delivery DECIMAL(10,2) DEFAULT 0;
ALTER TABLE caixa_fechamentos ADD COLUMN total_mesas DECIMAL(10,2) DEFAULT 0;
ALTER TABLE caixa_fechamentos ADD COLUMN total_geral DECIMAL(10,2) DEFAULT 0;
ALTER TABLE caixa_fechamentos ADD COLUMN qtd_pedidos_delivery INT DEFAULT 0;
ALTER TABLE caixa_fechamentos ADD COLUMN qtd_mesas INT DEFAULT 0;
ALTER TABLE caixa_fechamentos ADD COLUMN fechado_por VARCHAR(100);

-- Adiciona colunas faltantes em historico_mesas
ALTER TABLE historico_mesas ADD COLUMN mesa_numero VARCHAR(50);
ALTER TABLE historico_mesas ADD COLUMN total DECIMAL(10,2) DEFAULT 0;
ALTER TABLE historico_mesas ADD COLUMN itens TEXT;
ALTER TABLE historico_mesas ADD COLUMN fechado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
