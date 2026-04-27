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
        # Migração: adiciona licenca_vencimento se não existir
        if is_mysql():
            try:
                cursor.execute("ALTER TABLE users ADD COLUMN licenca_vencimento DATE DEFAULT NULL")
                conn.commit()
            except Exception:
                pass  # coluna já existe
        else:
            try:
                cursor.execute("ALTER TABLE users ADD COLUMN licenca_vencimento TEXT DEFAULT NULL")
                conn.commit()
            except Exception:
                pass  # coluna já existe

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

    def create_custom_admin(self, username: str, password: str, restaurante_id: int, role: str = 'atendente') -> bool:
        self.init_user_table()
        ph = "%s" if is_mysql() else "?"
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(f"SELECT id FROM users WHERE username = {ph}", (username,))
        if cursor.fetchone():
            return False
        password_hash = SecurityService.hash_password(password)
        cursor.execute(
            f"INSERT INTO users (username, password_hash, role, restaurante_id) VALUES ({ph}, {ph}, {ph}, {ph})",
            (username, password_hash, role, restaurante_id)
        )
        conn.commit()
        return True

    def get_user_by_username(self, username: str) -> Optional[User]:
        import logging
        ph = "%s" if is_mysql() else "?"
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            f"SELECT id, username, password_hash, role, restaurante_id FROM users WHERE username = {ph}",
            (username,)
        )
        row = cursor.fetchone()
        logging.warning(f"[DEBUG] get_user_by_username('{username}') row: {row}")
        conn.close()
        if row:
            user = User(id=row[0], username=row[1], password_hash=row[2], role=row[3], restaurante_id=row[4])
            logging.warning(f"[DEBUG] get_user_by_username('{username}') User: {user}")
            return user
        logging.warning(f"[DEBUG] get_user_by_username('{username}') returned None")
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

    def list_users(self, restaurante_id: int):
        self.init_user_table()
        conn = self.get_connection()
        cursor = conn.cursor()
        ph = "%s" if is_mysql() else "?"
        cursor.execute(
            f"SELECT id, username, role FROM users WHERE restaurante_id = {ph} AND role != 'superadmin' ORDER BY id",
            (restaurante_id,)
        )
        rows = cursor.fetchall()
        conn.close()
        return rows

    def delete_user(self, user_id: int, current_user_id: int, restaurante_id: int) -> bool:
        if user_id == current_user_id:
            return False
        ph = "%s" if is_mysql() else "?"
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            f"SELECT id FROM users WHERE id = {ph} AND restaurante_id = {ph} AND role != 'superadmin'",
            (user_id, restaurante_id)
        )
        if not cursor.fetchone():
            conn.close()
            return False
        cursor.execute(f"DELETE FROM users WHERE id = {ph}", (user_id,))
        conn.commit()
        conn.close()
        return True

    def list_admins(self):
        """Lista todos os usuários com role != superadmin (para o painel superadmin)."""
        self.init_user_table()
        conn = self.get_connection()
        cursor = conn.cursor()
        if is_mysql():
            cursor.execute("""
                SELECT id, username, role, licenca_vencimento
                FROM users
                WHERE role != 'superadmin' AND role != 'super_admin'
                ORDER BY id
            """)
        else:
            cursor.execute("""
                SELECT id, username, role, licenca_vencimento
                FROM users
                WHERE role != 'superadmin' AND role != 'super_admin'
                ORDER BY id
            """)
        rows = cursor.fetchall()
        conn.close()
        return rows

    def renovar_licenca(self, user_id: int, dias: int) -> bool:
        """Renova a licença somando X dias. Se vencida, conta a partir de hoje."""
        from datetime import date, timedelta
        conn = self.get_connection()
        cursor = conn.cursor()
        if is_mysql():
            cursor.execute("SELECT licenca_vencimento FROM users WHERE id = %s", (user_id,))
        else:
            cursor.execute("SELECT licenca_vencimento FROM users WHERE id = ?", (user_id,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            return False
        vencimento_atual = row[0]
        hoje = date.today()
        if vencimento_atual:
            venc = vencimento_atual if isinstance(vencimento_atual, date) else date.fromisoformat(str(vencimento_atual))
            nova_data = venc + timedelta(days=dias) if venc > hoje else hoje + timedelta(days=dias)
        else:
            nova_data = hoje + timedelta(days=dias)
        if is_mysql():
            cursor.execute("UPDATE users SET licenca_vencimento = %s WHERE id = %s", (nova_data, user_id))
        else:
            cursor.execute("UPDATE users SET licenca_vencimento = ? WHERE id = ?", (str(nova_data), user_id))
        conn.commit()
        conn.close()
        return True

    def bloquear_licenca(self, user_id: int) -> bool:
        """Define vencimento como ontem (bloqueia imediatamente)."""
        from datetime import date, timedelta
        ontem = date.today() - timedelta(days=1)
        conn = self.get_connection()
        cursor = conn.cursor()
        if is_mysql():
            cursor.execute("UPDATE users SET licenca_vencimento = %s WHERE id = %s", (ontem, user_id))
        else:
            cursor.execute("UPDATE users SET licenca_vencimento = ? WHERE id = ?", (str(ontem), user_id))
        conn.commit()
        conn.close()
        return True


# ========== PRODUTOS ==========

def listar_produtos(restaurante_id):
    ph = "%s" if is_mysql() else "?"
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(f"SELECT * FROM produtos WHERE ativo = 1 AND restaurante_id = {ph}", (restaurante_id,))
    rows = cursor.fetchall()
    conn.close()
    return rows

def adicionar_produto(nome, preco, categoria, emoji, restaurante_id, foto=None, descricao=None):
    ph = "%s" if is_mysql() else "?"
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        f"INSERT INTO produtos (nome, preco, categoria, emoji, foto, descricao, restaurante_id) VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph})",
        (nome, preco, categoria, emoji, foto, descricao, restaurante_id)
    )
    conn.commit()
    conn.close()

def editar_produto(id, nome, preco, categoria, emoji, restaurante_id, foto=None):
    ph = "%s" if is_mysql() else "?"
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        f"UPDATE produtos SET nome={ph}, preco={ph}, categoria={ph}, emoji={ph}, foto={ph} WHERE id={ph} AND restaurante_id={ph}",
        (nome, preco, categoria, emoji, foto, id, restaurante_id)
    )
    conn.commit()
    conn.close()

def desativar_produto(id, restaurante_id):
    ph = "%s" if is_mysql() else "?"
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(f"UPDATE produtos SET ativo = 0 WHERE id = {ph} AND restaurante_id = {ph}", (id, restaurante_id))
    conn.commit()
    conn.close()


# ========== ADICIONAIS ==========

def listar_adicionais(restaurante_id, categoria=None):
    """
    Lista adicionais ativos.
    Se categoria informada, retorna só os vinculados àquela categoria.
    """
    ph = "%s" if is_mysql() else "?"
    conn = get_connection()
    cursor = conn.cursor()
    if categoria:
        cursor.execute(f"""
            SELECT a.id, a.nome, a.preco
            FROM adicionais a
            INNER JOIN adicional_categoria ac ON a.id = ac.adicional_id
            WHERE a.ativo = 1 AND a.restaurante_id = {ph} AND ac.categoria = {ph}
        """, (restaurante_id, categoria))
    else:
        cursor.execute(f"SELECT id, nome, preco FROM adicionais WHERE ativo = 1 AND restaurante_id = {ph}", (restaurante_id,))
    rows = cursor.fetchall()
    conn.close()
    return rows

def listar_adicionais_com_categorias(restaurante_id):
    """Lista todos os adicionais com suas categorias vinculadas (para o painel admin)."""
    ph = "%s" if is_mysql() else "?"
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(f"SELECT id, nome, preco, ativo FROM adicionais WHERE restaurante_id = {ph} ORDER BY nome", (restaurante_id,))
    adicionais = cursor.fetchall()

    resultado = []
    for a in adicionais:
        cursor.execute(
            f"SELECT categoria FROM adicional_categoria WHERE adicional_id = {ph}", (a[0],)
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

def adicionar_adicional(nome, preco, categorias: list, restaurante_id):
    """
    Cadastra um adicional e vincula às categorias informadas.
    categorias: lista de strings, ex: ['Lanches', 'Porções']
    """
    ph = "%s" if is_mysql() else "?"
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        f"INSERT INTO adicionais (nome, preco, restaurante_id) VALUES ({ph}, {ph}, {ph})",
        (nome, preco, restaurante_id)
    )
    adicional_id = cursor.lastrowid
    for cat in categorias:
        cursor.execute(
            f"INSERT INTO adicional_categoria (adicional_id, categoria, restaurante_id) VALUES ({ph}, {ph}, {ph})",
            (adicional_id, cat, restaurante_id)
        )
    conn.commit()
    conn.close()
    return adicional_id

def editar_adicional(id, nome, preco, categorias: list, restaurante_id):
    """Atualiza nome/preço e recadastra as categorias vinculadas."""
    ph = "%s" if is_mysql() else "?"
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        f"UPDATE adicionais SET nome={ph}, preco={ph} WHERE id={ph} AND restaurante_id={ph}",
        (nome, preco, id, restaurante_id)
    )
    cursor.execute(f"DELETE FROM adicional_categoria WHERE adicional_id = {ph} AND restaurante_id = {ph}", (id, restaurante_id))
    for cat in categorias:
        cursor.execute(
            f"INSERT INTO adicional_categoria (adicional_id, categoria, restaurante_id) VALUES ({ph}, {ph}, {ph})",
            (id, cat, restaurante_id)
        )
    conn.commit()
    conn.close()

def desativar_adicional(id, restaurante_id):
    ph = "%s" if is_mysql() else "?"
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(f"UPDATE adicionais SET ativo = 0 WHERE id = {ph} AND restaurante_id = {ph}", (id, restaurante_id))
    conn.commit()
    conn.close()

def listar_categorias_produtos(restaurante_id):
    """Retorna lista de categorias únicas dos produtos ativos."""
    ph = "%s" if is_mysql() else "?"
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(f"SELECT DISTINCT categoria FROM produtos WHERE ativo = 1 AND restaurante_id = {ph} ORDER BY categoria", (restaurante_id,))
    rows = cursor.fetchall()
    conn.close()
    return [row[0] for row in rows]