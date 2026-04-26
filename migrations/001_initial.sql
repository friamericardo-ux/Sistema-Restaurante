CREATE TABLE IF NOT EXISTS users (
    id INT PRIMARY KEY AUTO_INCREMENT,
    username VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(50) DEFAULT 'staff',
    restaurante_id INT,
    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS produtos (
    id INT PRIMARY KEY AUTO_INCREMENT,
    nome VARCHAR(200) NOT NULL,
    preco DECIMAL(10,2) NOT NULL,
    descricao TEXT,
    imagem VARCHAR(255),
    categoria VARCHAR(100),
    ativo TINYINT(1) DEFAULT 1,
    restaurante_id INT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS adicionais (
    id INT PRIMARY KEY AUTO_INCREMENT,
    nome VARCHAR(200) NOT NULL,
    preco DECIMAL(10,2) NOT NULL,
    restaurante_id INT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS adicional_categoria (
    id INT PRIMARY KEY AUTO_INCREMENT,
    nome VARCHAR(200) NOT NULL,
    restaurante_id INT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS mesas (
    id INT PRIMARY KEY AUTO_INCREMENT,
    numero VARCHAR(50) NOT NULL,
    status VARCHAR(50) DEFAULT 'livre',
    restaurante_id INT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS itens (
    id INT PRIMARY KEY AUTO_INCREMENT,
    mesa_id INT,
    produto_id INT,
    quantidade INT DEFAULT 1,
    preco_unitario DECIMAL(10,2),
    restaurante_id INT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS pedidos_delivery (
    id INT PRIMARY KEY AUTO_INCREMENT,
    cliente_nome VARCHAR(200),
    cliente_telefone VARCHAR(50),
    endereco TEXT,
    status VARCHAR(50) DEFAULT 'pendente',
    total DECIMAL(10,2),
    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    restaurante_id INT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS historico_mesas (
    id INT PRIMARY KEY AUTO_INCREMENT,
    mesa_id INT,
    evento VARCHAR(100),
    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    restaurante_id INT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS configuracoes (
    id INT PRIMARY KEY AUTO_INCREMENT,
    chave VARCHAR(100) UNIQUE NOT NULL,
    valor TEXT,
    restaurante_id INT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS caixa_sessoes (
    id INT PRIMARY KEY AUTO_INCREMENT,
    aberto_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    fechado_em TIMESTAMP NULL,
    restaurante_id INT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS caixa_fechamentos (
    id INT PRIMARY KEY AUTO_INCREMENT,
    sessao_id INT,
    total DECIMAL(10,2),
    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    restaurante_id INT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS fechamentos_caixa (
    id INT PRIMARY KEY AUTO_INCREMENT,
    sessao_id INT,
    total DECIMAL(10,2),
    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    restaurante_id INT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS clientes_cache (
    id INT PRIMARY KEY AUTO_INCREMENT,
    telefone VARCHAR(50),
    nome VARCHAR(200),
    endereco TEXT,
    restaurante_id INT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;