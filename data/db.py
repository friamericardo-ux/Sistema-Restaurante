import sqlite3
import os
import re
from config import Config


def is_mysql():
    """Verifica se o banco configurado é MySQL"""
    return Config.DB_PATH.startswith('mysql')


# ========================
# WRAPPER PARA MYSQL
# ========================
class _MySQLCursor:
    """Converte placeholders ? para %s e traduz funções SQLite→MySQL"""
    def __init__(self, cursor):
        self._cursor = cursor

    def execute(self, sql, params=None):
        sql = sql.replace('?', '%s')
        sql = sql.replace("DATE('now', 'localtime')", 'CURDATE()')
        sql = sql.replace("DATE('now')", 'CURDATE()')
        # Converter DATE(coluna, 'localtime') → DATE(coluna) para MySQL
        sql = sql.replace(", 'localtime')", ")")
        # Converter CAST(strftime('%H', coluna) AS INTEGER) → HOUR(coluna) para MySQL
        sql = re.sub(r"CAST\(strftime\('%H',\s*(\w+)\)\s*AS\s*INTEGER\)", r"HOUR(\1)", sql)
        return self._cursor.execute(sql, params or ())

    def fetchone(self):
        return self._cursor.fetchone()

    def fetchall(self):
        return self._cursor.fetchall()

    @property
    def lastrowid(self):
        return self._cursor.lastrowid


class _MySQLConnection:
    """Faz pymysql se comportar como sqlite3.Connection"""
    def __init__(self, conn):
        self._conn = conn
        self._use_dict = False

    @property
    def row_factory(self):
        return self._use_dict

    @row_factory.setter
    def row_factory(self, value):
        self._use_dict = value is not None

    def cursor(self):
        import pymysql
        if self._use_dict:
            cur = self._conn.cursor(pymysql.cursors.DictCursor)
        else:
            cur = self._conn.cursor()
        return _MySQLCursor(cur)

    def execute(self, sql, params=None):
        cur = self.cursor()
        cur.execute(sql, params)
        return cur

    def commit(self):
        self._conn.commit()

    def close(self):
        self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            self._conn.commit()
        else:
            self._conn.rollback()
        self._conn.close()


# ========================
# CONEXÃO
# ========================
def get_connection():
    if is_mysql():
        import pymysql
        from urllib.parse import urlparse
        parsed = urlparse(Config.DB_PATH)
        conn = pymysql.connect(
        host=parsed.hostname or 'localhost',
        port=parsed.port or 3306,
        user=parsed.username or 'root',
        password=parsed.password or '',
        database=parsed.path.lstrip('/'),
        charset='utf8mb4',
        ssl_disabled=True,
    )
        return _MySQLConnection(conn)
    else:
        # Usa Config.DB_PATH, que pode ser absoluto ou relativo
        db_path = Config.DB_PATH
        # Se for relativo, torna relativo à raiz do projeto
        if not os.path.isabs(db_path):
            db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), db_path)
        return sqlite3.connect(db_path)


# ========================
# CRIAÇÃO DE TABELAS
# ========================
def init_db():
    if is_mysql():
        _init_mysql()
    else:
        _init_sqlite()


def _init_sqlite():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS mesas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        numero TEXT UNIQUE,
        total REAL DEFAULT 0
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS adicionais (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL,
        preco REAL NOT NULL DEFAULT 0.0,
        produto_id INTEGER DEFAULT NULL,
        ativo INTEGER DEFAULT 1,
        FOREIGN KEY (produto_id) REFERENCES produtos(id)
    )
    """)
    # Migração: adicionar produto_id se não existir (bancos antigos)
    cursor.execute("PRAGMA table_info(adicionais)")
    colunas = [col[1] for col in cursor.fetchall()]
    if 'produto_id' not in colunas:
        cursor.execute("ALTER TABLE adicionais ADD COLUMN produto_id INTEGER DEFAULT NULL")
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS produtos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL,
        preco REAL NOT NULL,
        categoria TEXT NOT NULL,
        emoji TEXT DEFAULT '🍽️',
        ativo INTEGER DEFAULT 1,
        foto TEXT DEFAULT NULL,
        descricao TEXT DEFAULT NULL
    )
    ''')
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS pedidos_delivery (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        cliente_nome TEXT,
        cliente_telefone TEXT,
        cliente_endereco TEXT,
        itens TEXT,
        taxa_entrega REAL DEFAULT 5.0,
        total REAL,
        status TEXT DEFAULT 'novo',
        criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS itens (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        mesa_id INTEGER,
        nome TEXT,
        preco REAL,
        quantidade INTEGER,
        observacao TEXT DEFAULT '',
        adicionado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (mesa_id) REFERENCES mesas(id)
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT DEFAULT 'admin'
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS historico_mesas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        mesa_numero TEXT,
        total REAL DEFAULT 0,
        itens TEXT,
        fechado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS caixa_fechamentos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        data TEXT,
        total_delivery REAL DEFAULT 0,
        total_mesas REAL DEFAULT 0,
        total_geral REAL DEFAULT 0,
        qtd_pedidos_delivery INTEGER DEFAULT 0,
        qtd_mesas INTEGER DEFAULT 0,
        fechado_por TEXT,
        fechado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    conn.commit()
    conn.close()


def _init_mysql():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS mesas (
        id INT PRIMARY KEY AUTO_INCREMENT,
        numero VARCHAR(50) UNIQUE,
        total DOUBLE DEFAULT 0
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS adicionais (
        id INT PRIMARY KEY AUTO_INCREMENT,
        nome VARCHAR(255) NOT NULL,
        preco DOUBLE NOT NULL DEFAULT 0.0,
        produto_id INT DEFAULT NULL,
        ativo TINYINT DEFAULT 1,
        FOREIGN KEY (produto_id) REFERENCES produtos(id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)
    # Migração: adicionar produto_id se não existir (bancos antigos)
    try:
        cursor.execute("ALTER TABLE adicionais ADD COLUMN produto_id INT DEFAULT NULL")
    except Exception:
        pass  # Coluna já existe
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS produtos (
        id INT PRIMARY KEY AUTO_INCREMENT,
        nome VARCHAR(255) NOT NULL,
        preco DOUBLE NOT NULL,
        categoria VARCHAR(100) NOT NULL,
        emoji VARCHAR(10) DEFAULT '🍽️',
        ativo TINYINT DEFAULT 1,
        foto VARCHAR(255) DEFAULT NULL,
        descricao TEXT DEFAULT NULL
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS pedidos_delivery (
        id INT PRIMARY KEY AUTO_INCREMENT,
        cliente_nome VARCHAR(255),
        cliente_telefone VARCHAR(50),
        cliente_endereco TEXT,
        itens TEXT,
        taxa_entrega DOUBLE DEFAULT 5.0,
        total DOUBLE,
        status VARCHAR(50) DEFAULT 'novo',
        criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS itens (
        id INT PRIMARY KEY AUTO_INCREMENT,
        mesa_id INT,
        nome VARCHAR(255),
        preco DOUBLE,
        quantidade INT,
        observacao VARCHAR(500) DEFAULT '',
        adicionado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (mesa_id) REFERENCES mesas(id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INT PRIMARY KEY AUTO_INCREMENT,
        username VARCHAR(100) UNIQUE NOT NULL,
        password_hash VARCHAR(255) NOT NULL,
        role VARCHAR(50) DEFAULT 'admin'
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS historico_mesas (
        id INT PRIMARY KEY AUTO_INCREMENT,
        mesa_numero VARCHAR(50),
        total DOUBLE DEFAULT 0,
        itens TEXT,
        fechado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS caixa_fechamentos (
        id INT PRIMARY KEY AUTO_INCREMENT,
        data VARCHAR(10),
        total_delivery DOUBLE DEFAULT 0,
        total_mesas DOUBLE DEFAULT 0,
        total_geral DOUBLE DEFAULT 0,
        qtd_pedidos_delivery INT DEFAULT 0,
        qtd_mesas INT DEFAULT 0,
        fechado_por VARCHAR(100),
        fechado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)

    conn.commit()
    conn.close()


# ========================
# FUNÇÕES DE ITENS
# ========================
def adicionar_item(mesa_id, nome, preco, quantidade=1, observacao=""):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO itens (mesa_id, nome, preco, quantidade, observacao)
        VALUES (?, ?, ?, ?, ?)
    """, (mesa_id, nome, preco, quantidade, observacao))

    cursor.execute("""
        UPDATE mesas
        SET total = (
            SELECT COALESCE(SUM(preco * quantidade), 0)
            FROM itens WHERE mesa_id = ?
        )
        WHERE id = ?
    """, (mesa_id, mesa_id))

    conn.commit()
    conn.close()


def listar_itens(mesa_id):
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    itens = conn.execute(
        "SELECT * FROM itens WHERE mesa_id = ?", (mesa_id,)
    ).fetchall()
    conn.close()
    return [dict(i) for i in itens]


def remover_item(item_id, mesa_id):
    conn = get_connection()

    conn.execute("DELETE FROM itens WHERE id = ?", (item_id,))

    # Recalcula total
    conn.execute("""
        UPDATE mesas
        SET total = (
            SELECT COALESCE(SUM(preco * quantidade), 0)
            FROM itens WHERE mesa_id = ?
        )
        WHERE id = ?
    """, (mesa_id, mesa_id))

    conn.commit()
    conn.close()


def fechar_mesa(mesa_id):
    conn = get_connection()
    # Apaga os itens e zera o total
    conn.execute("DELETE FROM itens WHERE mesa_id = ?", (mesa_id,))
    conn.execute("UPDATE mesas SET total = 0 WHERE id = ?", (mesa_id,))
    conn.commit()
    conn.close()
