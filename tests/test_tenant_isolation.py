import os
os.environ['DATABASE_URL'] = 'data/database.db'

import sys
from unittest.mock import MagicMock, patch

# Pre-populate sys.modules with a placeholder so that app.py is loaded
# with its __name__ as 'app' (not '__main__'), allowing other modules
# to import from it. The _garantir_* functions will be patched below.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Monkey-patch the _garantir_ functions via the module's own attribute
# BEFORE they're called. We import app here — it will trigger the function
# calls. Before that, we intercept via __builtins__ exec.
import builtins
import importlib

_orig_import = builtins.__import__

def _patched_import(name, *args, **kwargs):
    mod = _orig_import(name, *args, **kwargs)
    if name == 'app':
        mod._garantir_fechamentos_caixa = MagicMock()
        mod._garantir_configuracoes = MagicMock()
        mod._garantir_coluna_status = MagicMock()
    return mod

builtins.__import__ = _patched_import

from app import app as flask_app
from data.db import get_connection, is_mysql
from repository import UserRepository
from security import SecurityService

builtins.__import__ = _orig_import

import pytest


@pytest.fixture(autouse=True)
def app():
    flask_app.config['TESTING'] = True
    flask_app.config['WTF_CSRF_ENABLED'] = False
    flask_app.config['SESSION_COOKIE_SECURE'] = False
    yield flask_app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def db():
    conn = get_connection()
    yield conn
    conn.close()


def _criar_usuario_teste(username, password, restaurante_id):
    repo = UserRepository()
    existing = repo.get_user_by_username(username)
    if existing:
        return existing.id
    ph = "%s" if is_mysql() else "?"
    conn = get_connection()
    cursor = conn.cursor()
    hash_pw = SecurityService.hash_password(password)
    cursor.execute(
        f"INSERT INTO users (username, password_hash, role, restaurante_id) VALUES ({ph}, {ph}, {ph}, {ph})",
        (username, hash_pw, 'admin', restaurante_id)
    )
    conn.commit()
    user_id = cursor.lastrowid
    conn.close()
    return user_id


def _remover_usuario(username):
    ph = "%s" if is_mysql() else "?"
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(f"DELETE FROM users WHERE username = {ph}", (username,))
    conn.commit()
    conn.close()


def _login(client, username, password):
    return client.post('/login', data={
        'username': username,
        'password': password
    }, follow_redirects=False)


@pytest.fixture
def restaurante_a():
    return {'id': 1, 'slug': 'pantanal'}


@pytest.fixture(scope='function')
def restaurante_b(db):
    slug = 'test-b'
    ph = "%s" if is_mysql() else "?"
    cursor = db.cursor()
    cursor.execute(f"SELECT id FROM restaurantes WHERE slug = {ph}", (slug,))
    row = cursor.fetchone()
    if row:
        rid = row[0]
    else:
        cursor.execute(
            f"INSERT INTO restaurantes (slug, nome, ativo) VALUES ({ph}, {ph}, 1)",
            (slug, 'Restaurante Teste B')
        )
        db.commit()
        rid = cursor.lastrowid
    # Set restaurant as open for testing
    cursor.execute(f"""
        INSERT OR REPLACE INTO configuracoes (chave, valor, restaurante_id) VALUES ('horario_abertura', '00:00', {ph})
    """, (rid,))
    cursor.execute(f"""
        INSERT OR REPLACE INTO configuracoes (chave, valor, restaurante_id) VALUES ('horario_fechamento', '23:59', {ph})
    """, (rid,))
    cursor.execute(f"""
        INSERT OR REPLACE INTO configuracoes (chave, valor, restaurante_id) VALUES ('restaurante_ativo', '1', {ph})
    """, (rid,))
    cursor.execute(f"""
        INSERT OR REPLACE INTO configuracoes (chave, valor, restaurante_id) VALUES ('dias_funcionamento', 'Todos os dias', {ph})
    """, (rid,))
    db.commit()
    yield {'id': rid, 'slug': slug}
    cursor.execute(f"DELETE FROM configuracoes WHERE restaurante_id = {ph}", (rid,))
    cursor.execute(f"DELETE FROM restaurantes WHERE slug = {ph}", (slug,))
    db.commit()


@pytest.fixture
def session_a(client, restaurante_a):
    username = 'test_admin_a'
    _criar_usuario_teste(username, '123456', restaurante_a['id'])
    resp = _login(client, username, '123456')
    yield client
    _remover_usuario(username)


@pytest.fixture
def session_b(client, restaurante_b):
    username = 'test_admin_b'
    _criar_usuario_teste(username, '123456', restaurante_b['id'])
    resp = _login(client, username, '123456')
    yield client
    _remover_usuario(username)


def _criar_pedido_teste(db, restaurante_id):
    ph = "%s" if is_mysql() else "?"
    cursor = db.cursor()
    cursor.execute(f"""
        INSERT INTO pedidos_delivery
        (cliente_nome, cliente_telefone, cliente_endereco, itens, total, status, restaurante_id)
        VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph})
    """, ('Cliente Teste', '999999999', 'Rua A, 123', '[]', 50.0, 'novo', restaurante_id))
    db.commit()
    return cursor.lastrowid


def _remover_pedido(db, pedido_id):
    ph = "%s" if is_mysql() else "?"
    cursor = db.cursor()
    cursor.execute(f"DELETE FROM pedidos_delivery WHERE id = {ph}", (pedido_id,))
    db.commit()


def _criar_cliente_teste(db, restaurante_id):
    ph = "%s" if is_mysql() else "?"
    cursor = db.cursor()
    cursor.execute(f"""
        INSERT INTO clientes_cache (telefone, nome, endereco, restaurante_id)
        VALUES ({ph}, {ph}, {ph}, {ph})
    """, ('888888888', 'Cliente A', 'Rua Secreta, 456', restaurante_id))
    db.commit()


def _remover_cliente(db, telefone, restaurante_id):
    ph = "%s" if is_mysql() else "?"
    cursor = db.cursor()
    cursor.execute(
        f"DELETE FROM clientes_cache WHERE telefone = {ph} AND restaurante_id = {ph}",
        (telefone, restaurante_id)
    )
    db.commit()


class TestTenantIsolation:
    """Suite de testes de isolamento entre restaurantes."""

    def test_pedido_isolado(self, db, session_b, restaurante_a):
        pedido_a = _criar_pedido_teste(db, restaurante_a['id'])

        resp = session_b.get('/api/pedidos/delivery')
        assert resp.status_code == 200
        data = resp.get_json()

        ids_pedidos = [p['id'] for p in data.get('pedidos', [])]
        assert pedido_a not in ids_pedidos, \
            f"Pedido {pedido_a} do restaurante A vazou na listagem do restaurante B"

        _remover_pedido(db, pedido_a)

    def test_cliente_isolado(self, db, session_b, restaurante_a, restaurante_b):
        _criar_cliente_teste(db, restaurante_a['id'])

        resp = session_b.get(f'/api/cliente/888888888?slug={restaurante_b["slug"]}')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data.get('sucesso') is False, \
            "Cliente do restaurante A foi retornado ao consultar pelo restaurante B"

        _remover_cliente(db, '888888888', restaurante_a['id'])

    def test_query_param_ignorado(self, session_b, restaurante_a):
        resp = session_b.get(f'/api/cardapio?slug={restaurante_a["slug"]}')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data.get('sucesso') is True

    def test_body_restaurante_id_ignorado(self, db, session_b, restaurante_b):
        resp = session_b.post('/api/pedido', json={
            'slug': restaurante_b['slug'],
            'restaurante_id': 1,
            'nome': 'Teste Isolamento',
            'telefone': '777777777',
            'endereco': 'Rua Isolamento, 789',
            'itens': [{'nome': 'Item Teste', 'preco': 10.0, 'quantidade': 1}],
            'pagamento': 'dinheiro'
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data.get('sucesso') is True, f"Falha ao criar pedido: {data}"

        pedido_id = data['pedido_id']
        ph = "%s" if is_mysql() else "?"
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(f"SELECT restaurante_id FROM pedidos_delivery WHERE id = {ph}", (pedido_id,))
        row = cursor.fetchone()
        conn.close()
        assert row[0] == restaurante_b['id'], \
            f"Pedido criado no restaurante {row[0]} em vez de {restaurante_b['id']}"

        _remover_pedido(db, pedido_id)

    def test_check_status_sem_id_numerico(self, client):
        resp = client.get('/api/check-status/1')
        assert resp.status_code == 400

        resp = client.get('/api/check-status/pantanal')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'status' in data
