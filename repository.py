from config import Config
from models.user import User
from security import SecurityService
from typing import Optional
from data.db import get_connection, is_mysql


class UserRepository:
    def __init__(self):
        self.db_path = Config.DB_PATH

    def get_connection(self):
        return get_connection()

    def init_user_table(self):
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
        self.init_user_table()
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM users LIMIT 1")
        return cursor.fetchone() is not None

    def create_custom_admin(self, username: str, password: str, role: str = 'atendente') -> bool:
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
        self.init_user_table()
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, username, role FROM users ORDER BY id")
        rows = cursor.fetchall()
        conn.close()
        return rows

    def delete_user(self, user_id: int, current_user_id: int) -> bool:
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

def listar_adicionais(categoria=None):
    """
    Lista adicionais ativos.
    Se categoria informada, retorna só os vinculados àquela categoria.
    """
    conn = get_connection()
    cursor = conn.cursor()
    if categoria:
        cursor.execute("""
            SELECT a.id, a.nome, a.preco
            FROM adicionais a
            INNER JOIN adicional_categoria ac ON a.id = ac.adicional_id
            WHERE a.ativo = 1 AND ac.categoria = ?
        """, (categoria,))
    else:
        cursor.execute("SELECT id, nome, preco FROM adicionais WHERE ativo = 1")
    rows = cursor.fetchall()
    conn.close()
    return rows

def listar_adicionais_com_categorias():
    """Lista todos os adicionais com suas categorias vinculadas (para o painel admin)."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, nome, preco, ativo FROM adicionais ORDER BY nome")
    adicionais = cursor.fetchall()

    resultado = []
    for a in adicionais:
        cursor.execute(
            "SELECT categoria FROM adicional_categoria WHERE adicional_id = ?", (a[0],)
        )
        categorias = [row[0] for row in cursor.fetchall()]
        resultado.append({
            "id": a[0],
            "nome": a[1],
            "preco": a[2],
            "ativo": a[3],
            "categorias": categorias
        })
    conn.close()
    return resultado

def adicionar_adicional(nome, preco, categorias: list):
    """
    Cadastra um adicional e vincula às categorias informadas.
    categorias: lista de strings, ex: ['Lanches', 'Porções']
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO adicionais (nome, preco) VALUES (?, ?)",
        (nome, preco)
    )
    adicional_id = cursor.lastrowid
    for cat in categorias:
        cursor.execute(
            "INSERT INTO adicional_categoria (adicional_id, categoria) VALUES (?, ?)",
            (adicional_id, cat)
        )
    conn.commit()
    conn.close()
    return adicional_id

def editar_adicional(id, nome, preco, categorias: list):
    """Atualiza nome/preço e recadastra as categorias vinculadas."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE adicionais SET nome=?, preco=? WHERE id=?",
        (nome, preco, id)
    )
    cursor.execute("DELETE FROM adicional_categoria WHERE adicional_id = ?", (id,))
    for cat in categorias:
        cursor.execute(
            "INSERT INTO adicional_categoria (adicional_id, categoria) VALUES (?, ?)",
            (id, cat)
        )
    conn.commit()
    conn.close()

def desativar_adicional(id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE adicionais SET ativo = 0 WHERE id = ?", (id,))
    conn.commit()
    conn.close()

def listar_categorias_produtos():
    """Retorna lista de categorias únicas dos produtos ativos."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT categoria FROM produtos WHERE ativo = 1 ORDER BY categoria")
    rows = cursor.fetchall()
    conn.close()
    return [row[0] for row in rows]