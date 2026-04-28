-- 005_fix_delivery_and_mesas_v2.sql
-- Correção de esquema para alinhar com app.py e repository.py

-- Tabela pedidos_delivery
ALTER TABLE pedidos_delivery ADD COLUMN cliente_endereco TEXT AFTER cliente_telefone;
ALTER TABLE pedidos_delivery ADD COLUMN itens TEXT AFTER cliente_endereco;
ALTER TABLE pedidos_delivery ADD COLUMN taxa_entrega DOUBLE DEFAULT 5.0 AFTER itens;
ALTER TABLE pedidos_delivery ADD COLUMN forma_pagamento VARCHAR(50) DEFAULT '' AFTER total;
ALTER TABLE pedidos_delivery ADD COLUMN troco DOUBLE DEFAULT 0 AFTER forma_pagamento;

-- Tabela mesas
ALTER TABLE mesas ADD COLUMN total DOUBLE DEFAULT 0 AFTER numero;

-- Tabela itens
ALTER TABLE itens ADD COLUMN nome VARCHAR(255) AFTER mesa_id;
ALTER TABLE itens ADD COLUMN preco DOUBLE AFTER nome;
ALTER TABLE itens ADD COLUMN observacao VARCHAR(500) DEFAULT '' AFTER quantidade;

-- Garantir isolamento multi-tenant (restaurante_id)
ALTER TABLE pedidos_delivery ADD COLUMN restaurante_id INT DEFAULT 1;
ALTER TABLE mesas ADD COLUMN restaurante_id INT DEFAULT 1;
ALTER TABLE itens ADD COLUMN restaurante_id INT DEFAULT 1;
ALTER TABLE produtos ADD COLUMN restaurante_id INT DEFAULT 1;
ALTER TABLE adicionais ADD COLUMN restaurante_id INT DEFAULT 1;
ALTER TABLE adicional_categoria ADD COLUMN restaurante_id INT DEFAULT 1;
ALTER TABLE users ADD COLUMN restaurante_id INT DEFAULT 1;
ALTER TABLE historico_mesas ADD COLUMN restaurante_id INT DEFAULT 1;
ALTER TABLE caixa_fechamentos ADD COLUMN restaurante_id INT DEFAULT 1;
ALTER TABLE fechamentos_caixa ADD COLUMN restaurante_id INT DEFAULT 1;
ALTER TABLE caixa_sessoes ADD COLUMN restaurante_id INT DEFAULT 1;
ALTER TABLE clientes_cache ADD COLUMN restaurante_id INT DEFAULT 1;
ALTER TABLE configuracoes ADD COLUMN restaurante_id INT DEFAULT 1;
