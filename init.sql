CREATE DATABASE IF NOT EXISTS sistema_restaurante;
USE sistema_restaurante;

CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    email VARCHAR(100),
    role VARCHAR(20) DEFAULT 'admin',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE USER IF NOT EXISTS 'pantanal'@'%' IDENTIFIED BY 'pantanal123';
GRANT ALL PRIVILEGES ON sistema_restaurante.* TO 'pantanal'@'%';
FLUSH PRIVILEGES;