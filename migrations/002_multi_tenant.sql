-- Migration 002: Multi-tenant
-- Adiciona restaurante_id em todas as tabelas. Dados existentes preservados.

CREATE TABLE IF NOT EXISTS restaurantes (
    id INT PRIMARY KEY AUTO_INCREMENT,
    slug VARCHAR(100) UNIQUE NOT NULL,
    nome VARCHAR(200) NOT NULL,
    ativo TINYINT(1) DEFAULT 1,
    licenca_vencimento DATE NULL,
    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

INSERT IGNORE INTO restaurantes (id, slug, nome, ativo)
VALUES (1, 'pantanal', 'Pantanal', 1);

ALTER TABLE produtos ADD COLUMN restaurante_id INT NOT NULL DEFAULT 1;
ALTER TABLE adicionais ADD COLUMN restaurante_id INT NOT NULL DEFAULT 1;
ALTER TABLE adicional_categoria ADD COLUMN restaurante_id INT NOT NULL DEFAULT 1;
ALTER TABLE pedidos_delivery ADD COLUMN restaurante_id INT NOT NULL DEFAULT 1;
ALTER TABLE mesas ADD COLUMN restaurante_id INT NOT NULL DEFAULT 1;
ALTER TABLE itens ADD COLUMN restaurante_id INT NOT NULL DEFAULT 1;
ALTER TABLE historico_mesas ADD COLUMN restaurante_id INT NOT NULL DEFAULT 1;
ALTER TABLE configuracoes ADD COLUMN restaurante_id INT NOT NULL DEFAULT 1;
ALTER TABLE caixa_sessoes ADD COLUMN restaurante_id INT NOT NULL DEFAULT 1;
ALTER TABLE caixa_fechamentos ADD COLUMN restaurante_id INT NOT NULL DEFAULT 1;
ALTER TABLE fechamentos_caixa ADD COLUMN restaurante_id INT NOT NULL DEFAULT 1;
ALTER TABLE clientes_cache ADD COLUMN restaurante_id INT NOT NULL DEFAULT 1;
ALTER TABLE users ADD COLUMN restaurante_id INT NOT NULL DEFAULT 1