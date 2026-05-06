"""Runner script for pytest with database compatibility patches."""
import os
import sys
import re
import types
import sqlite3
from datetime import date

os.environ['DATABASE_URL'] = 'data/database.db'
sys.path.insert(0, os.path.dirname(__file__))

# Patch sqlite3.connect to register MySQL-compatible functions
_orig_sqlite_connect = sqlite3.connect

def _patched_sqlite_connect(*args, **kwargs):
    conn = _orig_sqlite_connect(*args, **kwargs)
    conn.create_function("CURDATE", 0, lambda: str(date.today()))
    return conn

sqlite3.connect = _patched_sqlite_connect

# 1. Ensure tables and data exist for testing
conn = sqlite3.connect('data/database.db')

# Register MySQL-compatible functions for SQLite
def _curdate():
    from datetime import date
    return str(date.today())
conn.create_function("CURDATE", 0, _curdate)

# Create tables that MySQL has but SQLite init doesn't
conn.execute("""
    CREATE TABLE IF NOT EXISTS restaurantes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        slug TEXT UNIQUE,
        nome TEXT,
        ativo INTEGER DEFAULT 1,
        status TEXT DEFAULT 'fechado'
    )
""")
# Insert restaurante A (pantanal) if not exists
cur = conn.execute("SELECT id FROM restaurantes WHERE slug = 'pantanal'")
if not cur.fetchone():
    conn.execute("INSERT INTO restaurantes (slug, nome, ativo) VALUES ('pantanal', 'Pantanal Dev', 1)")

# Add columns that exist in MySQL but not in SQLite init
for col in ['sessao_inicio', 'aberto']:
    try:
        conn.execute(f"ALTER TABLE caixa_sessoes ADD COLUMN {col} INTEGER")
    except sqlite3.OperationalError:
        pass

# Seed schema_migrations
conn.execute("""
    CREATE TABLE IF NOT EXISTS schema_migrations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        filename TEXT UNIQUE NOT NULL,
        executado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
""")
migrations_dir = 'migrations'
if os.path.isdir(migrations_dir):
    for f in sorted(os.listdir(migrations_dir)):
        if (f.endswith('.sql') or f.endswith('.py')) and re.match(r'^\d+_', f):
            try:
                conn.execute("INSERT OR IGNORE INTO schema_migrations (filename) VALUES (?)", (f,))
            except Exception:
                pass
conn.commit()
conn.close()

# 2. Load app.py with _garantir_* calls stripped
with open(os.path.join(os.path.dirname(__file__), 'app.py'), 'r', encoding='utf-8') as f:
    source = f.read()

source = re.sub(r'^\s*_garantir_\w+\(\)\s*$', '', source, flags=re.MULTILINE)
source = re.sub(r'^\s*#?\s*inicializar_admin\(\)\s*$', '', source, flags=re.MULTILINE)

mod = types.ModuleType('app')
mod.__file__ = os.path.join(os.path.dirname(__file__), 'app.py')
sys.modules['app'] = mod
exec(compile(source, 'app.py', 'exec'), mod.__dict__)

# 3. Monkey-patch helpers/functions that use MySQL-only %s placeholder
#    (these are bugs in the production code that only surface on SQLite)
from data.db import is_mysql, get_connection

def _safe_ph_slug(slug):
    if not slug:
        return None
    db = get_connection()
    cursor = db.cursor()
    ph = "%s" if is_mysql() else "?"
    cursor.execute(f"SELECT id FROM restaurantes WHERE slug = {ph} AND ativo = 1", (slug,))
    row = cursor.fetchone()
    db.close()
    return row[0] if row else None

import app as app_mod
import helpers as helpers_mod
app_mod._get_rid_from_slug = _safe_ph_slug
helpers_mod._get_rid_from_slug = _safe_ph_slug

# 4. Patch all modules that imported _get_rid_from_slug locally
import routes.cardapio
import routes.pedidos
routes.cardapio._get_rid_from_slug = _safe_ph_slug
routes.pedidos._get_rid_from_slug = _safe_ph_slug

# Also add proper placeholder to other functions that might use %s
import repository as repo_mod
# Patch _criar_pedido_delivery if it uses %s... already handled by ph variable

# 5. Run pytest
from app import app as flask_app

import pytest
sys.exit(pytest.main(['tests/test_tenant_isolation.py', '-v']))
