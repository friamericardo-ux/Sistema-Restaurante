

from config import Config
from models.user import User
from security import SecurityService
from typing import Optional
from data.db import get_connection, is_mysql

class UserRepository:
    def __init__(self):
       self.db_path = Config.DB_PATH

    def get_connection(self):
        """Retorna conexão com o banco (SQLite ou MySQL)"""
        return get_connection()

    def init_user_table(self):
        """Cria a tabela de usuários se não existir"""
        conn = self.get_connection()
        cursor = conn.cursor()
        if is_mysql():
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INT PRIMARY KEY AUTO_INCREMENT,
                    username VARCHAR(100) UNIQUE NOT NULL,
                    password_hash VARCHAR(255) NOT NULL,
                    role VARCHAR(50) DEFAULT 'admin'
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
        else:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    role TEXT DEFAULT 'admin'
                )
            """)
        conn.commit()

    def create_admin(self):
        """Cria usuário admin se não existir"""
        self.init_user_table()
        
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM users WHERE username = ?", (Config.ADMIN_USER,))
        if cursor.fetchone():
            return False
        password_hash = SecurityService.hash_password(Config.ADMIN_PASS)
        cursor.execute(
            "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
            (Config.ADMIN_USER, password_hash, "admin")
        )
        conn.commit()
        return True

    def has_any_user(self) -> bool:
        """Retorna True se já existe algum usuário cadastrado"""
        self.init_user_table()
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM users LIMIT 1")
        return cursor.fetchone() is not None

    def create_custom_admin(self, username: str, password: str, role: str = 'atendente') -> bool:
        """Cria um usuário com o perfil indicado"""
        self.init_user_table()
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
        if cursor.fetchone():
            return False
        password_hash = SecurityService.hash_password(password)
        cursor.execute(
            "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
            (username, password_hash, role)
        )
        conn.commit()
        return True

    def get_user_by_username(self, username: str) -> Optional[User]:
        """Busca usuário pelo nome"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
                "SELECT id, username, password_hash, role FROM users WHERE username = ?",
                (username,)
            )
        row = cursor.fetchone()
        conn.close()
        if row:
                return User(id=row[0], username=row[1], password_hash=row[2], role=row[3])
        return None

    def update_password(self, user_id: int, new_password: str) -> None:
        """Atualiza a senha de um usuário"""
        new_hash = SecurityService.hash_password(new_password)
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE users SET password_hash = ? WHERE id = ?",
            (new_hash, user_id)
        )
        conn.commit()
        conn.close()

    def list_users(self):
        """Lista todos os usuários cadastrados"""
        self.init_user_table()
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, username, role FROM users ORDER BY id")
        rows = cursor.fetchall()
        conn.close()
        return rows

    def delete_user(self, user_id: int, current_user_id: int) -> bool:
        """Remove um usuário (não permite remover a si mesmo)"""
        if user_id == current_user_id:
            return False
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()
        conn.close()
        return True

# ========== PRODUTOS ==========

def listar_produtos():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM produtos WHERE ativo = 1")
    rows = cursor.fetchall()
    conn.close()
    return rows

def adicionar_produto(nome, preco, categoria, emoji, foto=None, descricao=None):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO produtos (nome, preco, categoria, emoji, foto, descricao) VALUES (?, ?, ?, ?, ?, ?)",
        (nome, preco, categoria, emoji, foto, descricao)
    )
    conn.commit()
    conn.close()

def editar_produto(id, nome, preco, categoria, emoji, foto=None):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE produtos SET nome=?, preco=?, categoria=?, emoji=?, foto=? WHERE id=?",
        (nome, preco, categoria, emoji, foto, id)
    )
    conn.commit()
    conn.close()

def desativar_produto(id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE produtos SET ativo = 0 WHERE id = ?", (id,))
    conn.commit()
    conn.close()

# ========== ADICIONAIS ==========

def listar_adicionais(produto_id=None):
    conn = get_connection()
    cursor = conn.cursor()
    if produto_id is not None:
        cursor.execute("SELECT categoria FROM produtos WHERE id = ?", (produto_id,))
        row = cursor.fetchone()
        categoria_produto = row[0] if row else None
        cursor.execute("""
            SELECT * FROM adicionais 
            WHERE ativo = 1 AND (
                produto_id = ? 
                OR categoria = ?
                OR (produto_id IS NULL AND categoria IS NULL)
            )
        """, (produto_id, categoria_produto))
    else:
        cursor.execute("SELECT * FROM adicionais WHERE ativo = 1")
    rows = cursor.fetchall()
    conn.close()
    return rows

def adicionar_adicional(nome, preco, produto_id=None, categoria=None):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO adicionais (nome, preco, produto_id, categoria) VALUES (?, ?, ?, ?)",
        (nome, preco, produto_id, categoria)
    )
    conn.commit()
    conn.close()

def desativar_adicional(id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE adicionais SET ativo = 0 WHERE id = ?", (id,))
    conn.commit()
    conn.close()