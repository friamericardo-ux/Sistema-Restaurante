import json
from datetime import datetime, timedelta
import os
import logging
import sqlite3
from repository import (
    listar_adicionais, listar_adicionais_com_categorias,
    listar_produtos, adicionar_produto, editar_produto, desativar_produto,
    adicionar_adicional, editar_adicional, desativar_adicional, excluir_adicional,
    listar_categorias_produtos, obter_resumo_dashboard,
    listar_mesas_com_itens, abrir_mesa as repo_abrir_mesa,
    adicionar_item_mesa, remover_item_mesa,
    fechar_mesa_com_historico, criar_pedido_delivery,
    get_mesa, pedir_conta_mesa, fechar_mesa as repo_fechar_mesa
)
import urllib.parse
from services.whatsapp_service import WhatsAppService
from repository import UserRepository
from security import SecurityService
from config import Config
from flask import Flask, render_template, jsonify, request, session, redirect, url_for
from data.db import init_db, get_connection, is_mysql
from functools import wraps
from werkzeug.utils import secure_filename
from flask_talisman import Talisman
from flask_cors import CORS
from PIL import Image
import io
from extensions import csrf, limiter
from routes.auth import auth_bp
from routes.cardapio import cardapio_bp
from routes.pedidos import pedidos_bp, route_criar_pedido
from routes.mesas import mesas_bp
from routes.delivery import delivery_bp
from routes.caixa import caixa_bp
from routes.whatsapp import whatsapp_bp

from helpers import get_restaurante_id_or_403, get_pagination_params, get_config, set_config, get_status_restaurante, verificar_horario_funcionamento, _get_rid_from_slug, formatar_dias, parsear_dias

def inicializar_admin():
    from repository import UserRepository
    from security import SecurityService
    repo = UserRepository()
    user = repo.get_user_by_username(Config.ADMIN_USER)
    if not user:
        repo.create_admin()
        print(f"Admin '{Config.ADMIN_USER}' criado automaticamente.")

# Logging de segurança
logging.basicConfig(level=logging.WARNING,
                    format='%(asctime)s - %(levelname)s - %(message)s')

app = Flask(__name__)
from werkzeug.middleware.proxy_fix import ProxyFix
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=2, x_host=1)

CORS(app, origins=[
    "https://pantanaldev.com.br",
    "https://*.pantanaldev.com.br"
], supports_credentials=True)

app.secret_key = Config.SECRET_KEY

# Proteção CSRF + Rate limiting
csrf.init_app(app)
limiter.init_app(app)

# Blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(cardapio_bp)
app.register_blueprint(pedidos_bp)
app.register_blueprint(mesas_bp)
app.register_blueprint(delivery_bp)
app.register_blueprint(caixa_bp)
app.register_blueprint(whatsapp_bp)

# Headers de segurança
Talisman(app,
    force_https=False,
    content_security_policy={
        'default-src': "'self'",
        'script-src': "'self' 'unsafe-inline' maps.googleapis.com",
        'style-src': "'self' 'unsafe-inline' fonts.googleapis.com",
        'img-src': "'self' data: maps.gstatic.com *.googleapis.com *.gstatic.com",
        'font-src': "'self' data: fonts.gstatic.com",
        'connect-src': "'self' maps.googleapis.com *.googleapis.com https://pantanaldev.com.br https://*.pantanaldev.com.br",
    },
    session_cookie_secure=False, 
)

@app.errorhandler(429)
def ratelimit_handler(e):
    return jsonify({"sucesso": False, "erro": e.description or "Muitas requisicoes. Tente novamente mais tarde."}), 429

@app.context_processor
def inject_global_vars():
    # Cor primária vinda do banco ou fallback Indigo
    cor = get_config("cor_primaria", "#6366F1", restaurante_id=session.get('restaurante_id', 1))

    # Slug do restaurante do usuário logado (para link do cardápio na sidebar)
    # Retorna None em rotas públicas ou para superadmin sem restaurante vinculado
    restaurante_slug = None
    rid = session.get('restaurante_id')
    if rid:
        try:
            _db = get_connection()
            _cursor = _db.cursor()
            ph = "%s" if is_mysql() else "?"
            _cursor.execute(f"SELECT slug FROM restaurantes WHERE id = {ph}", (rid,))
            row = _cursor.fetchone()
            _db.close()
            if row:
                restaurante_slug = row[0] if not isinstance(row, dict) else row.get('slug')
        except Exception:
            pass  # banco pode não ter tabela restaurantes em dev local

    return dict(cor_primaria=cor, restaurante_slug=restaurante_slug)

# Extensões e tamanho máximo de upload
EXTENSOES_PERMITIDAS = {'.jpg', '.jpeg', '.png', '.webp', '.gif'}
MAX_FILE_SIZE = 16 * 1024 * 1024  # 16MB
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE
UPLOAD_FOLDER = os.path.join(app.static_folder, 'uploads', 'produtos')

def extensao_valida(filename):
    return os.path.splitext(filename)[1].lower() in EXTENSOES_PERMITIDAS

# PIN de segurança extra para o superadmin
SUPERADMIN_PIN = os.getenv('SUPERADMIN_PIN', '2026super')

app.config.update(
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    PERMANENT_SESSION_LIFETIME=timedelta(hours=8)
)
init_db()
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def _garantir_fechamentos_caixa():
    db = get_connection()
    cursor = db.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS fechamentos_caixa (
            id INT PRIMARY KEY AUTO_INCREMENT,
            data VARCHAR(10),
            total_faturado DOUBLE DEFAULT 0,
            total_pedidos INT DEFAULT 0,
            total_entregas INT DEFAULT 0,
            valor_entregas DOUBLE DEFAULT 0,
            criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)
    db.commit()
    db.close()

_garantir_fechamentos_caixa()


@app.before_request
def verificar_licenca_global():
    from datetime import date

    rotas_liberadas = {
        'auth.login_web', 'auth.logout', 'static',
        'cardapio_cliente', 'api_cardapio', 'api_adicionais',
        'criar_pedido', 'api_configuracoes',
        'api_restaurante_por_slug',
        'superadmin_pin', 'superadmin_pin_post',
    }

    if request.endpoint is None:
        return
    if request.endpoint in rotas_liberadas:
        return

    if session.get('role') in ('superadmin', 'super_admin'):
        return

    if not session.get('user_id'):
        return

    try:
        db = get_connection()
        cursor = db.cursor()
        if is_mysql():
            cursor.execute("""
                SELECT u.licenca_vencimento
                FROM users u
                WHERE u.role = 'admin'
                ORDER BY u.id LIMIT 1
            """)
        else:
            cursor.execute("""
                SELECT licenca_vencimento
                FROM users
                WHERE role = 'admin'
                ORDER BY id LIMIT 1
            """)
        row = cursor.fetchone()
        db.close()

        if row and row[0]:
            venc = row[0] if isinstance(row[0], date) else date.fromisoformat(str(row[0]))
            if venc < date.today():
                session.clear()
                return render_template('licenca_vencida.html'), 403
    except Exception:
        pass

    rid = session.get('restaurante_id')
    if rid:
        verificar_horario_funcionamento(rid)



def _garantir_caixa_sessoes():
    db = get_connection()
    cursor = db.cursor()
    if is_mysql():
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS caixa_sessoes (
                id INT PRIMARY KEY AUTO_INCREMENT,
                aberto_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)
    else:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS caixa_sessoes (
                id INTEGER PRIMARY KEY,
                aberto_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
    db.commit()
    db.close()

_garantir_caixa_sessoes()


def _garantir_clientes_cache():
    db = get_connection()
    cursor = db.cursor()
    if is_mysql():
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS clientes_cache (
                telefone VARCHAR(20),
                nome VARCHAR(100),
                endereco VARCHAR(255),
                atualizado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                restaurante_id INT NOT NULL DEFAULT 1,
                PRIMARY KEY (telefone, restaurante_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)
    else:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS clientes_cache (
                telefone TEXT,
                nome TEXT,
                endereco TEXT,
                atualizado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                restaurante_id INTEGER NOT NULL DEFAULT 1,
                PRIMARY KEY (telefone, restaurante_id)
            )
        """)
    db.commit()
    db.close()

_garantir_clientes_cache()


def _garantir_configuracoes():
    db = get_connection()
    cursor = db.cursor()
    if is_mysql():
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS configuracoes (
                chave VARCHAR(100) NOT NULL,
                valor TEXT,
                restaurante_id INT NOT NULL DEFAULT 1,
                atualizado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                PRIMARY KEY (chave, restaurante_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)
        db.commit()
        # Migração: adiciona restaurante_id se a tabela já existia sem ela
        cursor.execute("SHOW COLUMNS FROM configuracoes LIKE 'restaurante_id'")
        if not cursor.fetchone():
            cursor.execute("ALTER TABLE configuracoes ADD COLUMN restaurante_id INT NOT NULL DEFAULT 1")
            db.commit()
        # Migração: corrige PRIMARY KEY se ainda for só (chave)
        try:
            cursor.execute("ALTER TABLE configuracoes DROP PRIMARY KEY")
            cursor.execute("ALTER TABLE configuracoes ADD PRIMARY KEY (chave, restaurante_id)")
            db.commit()
        except Exception:
            pass  # PK já está correta
    else:
        # SQLite: recria a tabela se não tiver restaurante_id (preserva dados como restaurante_id=1)
        cursor.execute("PRAGMA table_info(configuracoes)")
        colunas = [row[1] for row in cursor.fetchall()]
        if not colunas:
            cursor.execute("""
                CREATE TABLE configuracoes (
                    chave TEXT NOT NULL,
                    valor TEXT,
                    restaurante_id INTEGER NOT NULL DEFAULT 1,
                    atualizado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (chave, restaurante_id)
                )
            """)
        elif 'restaurante_id' not in colunas:
            cursor.execute("""
                CREATE TABLE configuracoes_nova (
                    chave TEXT NOT NULL,
                    valor TEXT,
                    restaurante_id INTEGER NOT NULL DEFAULT 1,
                    atualizado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (chave, restaurante_id)
                )
            """)
            cursor.execute("INSERT INTO configuracoes_nova (chave, valor, atualizado_em) SELECT chave, valor, atualizado_em FROM configuracoes")
            cursor.execute("DROP TABLE configuracoes")
            cursor.execute("ALTER TABLE configuracoes_nova RENAME TO configuracoes")
        db.commit()
    db.close()

_garantir_configuracoes()


def _garantir_coluna_status():
    db = get_connection()
    cursor = db.cursor()
    if is_mysql():
        cursor.execute("SHOW COLUMNS FROM restaurantes LIKE 'status'")
        if not cursor.fetchone():
            cursor.execute("ALTER TABLE restaurantes ADD COLUMN status VARCHAR(20) DEFAULT 'fechado'")
            db.commit()
    else:
        cursor.execute("PRAGMA table_info(restaurantes)")
        cols = [r[1] for r in cursor.fetchall()]
        if 'status' not in cols:
            cursor.execute("ALTER TABLE restaurantes ADD COLUMN status TEXT DEFAULT 'fechado'")
            db.commit()
    db.close()

_garantir_coluna_status()





from helpers import _get_sessao_inicio, login_required, admin_required, caixa_or_admin_required, superadmin_required


def licenca_ativa(username: str) -> bool:
    """Verifica se o admin tem licença válida. Superadmin sempre passa."""
    from datetime import date
    repo = UserRepository()
    user = repo.get_user_by_username(username)
    if not user:
        return False
    if user.role in ('superadmin', 'super_admin'):
        return True
    db = get_connection()
    cursor = db.cursor()
    if is_mysql():
        cursor.execute("SELECT licenca_vencimento FROM users WHERE id = %s", (user.id,))
    else:
        cursor.execute("SELECT licenca_vencimento FROM users WHERE id = ?", (user.id,))
    row = cursor.fetchone()
    db.close()
    if not row or not row[0]:
        return True  # sem data = sem restrição ainda
    vencimento = row[0] if isinstance(row[0], date) else date.fromisoformat(str(row[0]))
    return vencimento >= date.today()


@app.route("/setup", methods=['GET', 'POST'])
@limiter.limit("120/minute")
def setup():
    """Configuração inicial — só acessível se não há usuários cadastrados"""
    repo = UserRepository()
    if repo.has_any_user():
        return redirect(url_for('auth.login_web'))

    erro = None
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        confirmar = request.form.get('confirmar', '')

        if not username or not password:
            erro = 'Preencha usuário e senha.'
        elif len(password) < 6:
            erro = 'A senha deve ter pelo menos 6 caracteres.'
        elif password != confirmar:
            erro = 'As senhas não coincidem.'
        else:
            repo.create_custom_admin(username, password)
            return redirect(url_for('auth.login_web'))

    return render_template('setup.html', erro=erro)

# ========================
# ROTAS PRINCIPAIS
# ========================
@app.route('/')
@limiter.limit("120/minute")
def home():
    return render_template('landing.html')
@app.route("/dashboard")
@login_required
def index():
    role = session.get('role')
    restaurante_slug = None
    rid = get_restaurante_id_or_403()
    db = get_connection()
    cursor = db.cursor()
    cursor.execute("SELECT slug FROM restaurantes WHERE id = %s", (rid,))
    row = cursor.fetchone()
    db.close()
    if row:
        restaurante_slug = row[0]
    if role == 'admin':
        return render_template('dashboard.html', restaurante_slug=restaurante_slug)
    elif role in ('atendente', 'garcom'):
        return redirect(url_for('mesas.mesas'))
    elif role == 'caixa':
        return render_template('caixa.html')
    elif role in ('superadmin', 'super_admin'):
        return render_template('dashboard.html', restaurante_slug=restaurante_slug)
    else:
        return redirect(url_for('auth.login_web'))


@app.route("/api/dashboard/resumo")
@login_required
def dashboard_resumo():
    """Retorna contadores para o dashboard"""
    try:
        rid = get_restaurante_id_or_403()
        resumo = obter_resumo_dashboard(rid)
        return jsonify({"sucesso": True, **resumo})
    except Exception as e:
        app.logger.error(f"Erro no dashboard_resumo: {e}")
        return jsonify({"sucesso": False, "erro": "Erro interno ao buscar resumo"}), 500

@app.route("/api/mesa/item", methods=["POST"])
@csrf.exempt
@login_required
def adicionar_item():
    try:
        dados = request.get_json()
        num = str(dados.get("numero"))
        rid = get_restaurante_id_or_403()
        
        nome = dados.get("nome")
        preco = float(dados.get("preco"))
        quantidade = int(dados.get("quantidade", 1))
        observacao = dados.get("observacao", "")

        sucesso, erro = adicionar_item_mesa(num, nome, preco, quantidade, observacao, rid)
        return jsonify({"sucesso": sucesso, "erro": erro})
    except Exception as e:
        app.logger.error(f"Erro no adicionar_item: {e}")
        return jsonify({"sucesso": False, "erro": "Erro ao adicionar item"}), 500

@app.route("/api/mesa/item/remover", methods=["POST"])
@csrf.exempt
@login_required
def remover_item():
    try:
        dados = request.get_json()
        item_id = int(dados.get("id"))
        rid = get_restaurante_id_or_403()
        
        sucesso, erro = remover_item_mesa(item_id, rid)
        return jsonify({"sucesso": sucesso, "erro": erro})
    except Exception as e:
        app.logger.error(f"Erro no remover_item: {e}")
        return jsonify({"sucesso": False, "erro": "Erro ao remover item"}), 500

@app.route("/api/mesa/fechar", methods=["POST"])
@csrf.exempt
@login_required
def route_fechar_mesa():
    try:
        role = session.get('role')
        if role not in ('admin', 'caixa', 'superadmin', 'super_admin'):
            return jsonify({"sucesso": False, "erro": "Permissão negada"}), 403

        dados = request.get_json()
        num = str(dados.get("numero"))
        rid = get_restaurante_id_or_403()
        
        sucesso, erro = fechar_mesa_com_historico(num, rid)
        return jsonify({"sucesso": sucesso, "erro": erro})
    except Exception as e:
        app.logger.error(f"Erro no fechar_mesa: {e}")
        return jsonify({"sucesso": False, "erro": "Erro ao fechar mesa"}), 500

@app.route("/api/mesa/pedir-conta/<int:mesa_id>", methods=["POST"])
@csrf.exempt
@login_required
def pedir_conta(mesa_id):
    """Pedir conta da mesa - qualquer perfil autenticado"""
    try:
        rid = get_restaurante_id_or_403()
        mesa = get_mesa(mesa_id, rid)
        if not mesa:
            return jsonify({"sucesso": False, "erro": "Mesa não encontrada"}), 404
        sucesso, erro = pedir_conta_mesa(mesa_id, rid)
        return jsonify({"sucesso": sucesso, "erro": erro})
    except Exception as e:
        app.logger.error(f"Erro no pedir_conta: {e}")
        return jsonify({"sucesso": False, "erro": "Erro ao pedir conta"}), 500

@app.route("/api/mesa/fechar/<int:mesa_id>", methods=["POST"])
@csrf.exempt
@login_required
def route_fechar_mesa_id(mesa_id):
    """Fechar mesa - somente admin, caixa ou superadmin"""
    try:
        role = session.get('role')
        if role not in ('admin', 'caixa', 'superadmin', 'super_admin'):
            return jsonify({"sucesso": False, "erro": "Permissão negada"}), 403
        rid = get_restaurante_id_or_403()
        mesa = get_mesa(mesa_id, rid)
        if not mesa:
            return jsonify({"sucesso": False, "erro": "Mesa não encontrada"}), 404
        sucesso, erro = repo_fechar_mesa(mesa_id, rid)
        return jsonify({"sucesso": sucesso, "erro": erro})
    except Exception as e:
        app.logger.error(f"Erro no fechar_mesa_id: {e}")
        return jsonify({"sucesso": False, "erro": "Erro ao fechar mesa"}), 500





# ROTAS PARA CLIENTES (DELIVERY)


@app.route("/api/pedido/whatsapp")
@login_required
def whatsapp_pedido():
    """Gera link otimizado para WhatsApp usando o serviço"""
    pedido_id = request.args.get("pedido_id")
    
    db = get_connection()
    db.row_factory = sqlite3.Row
    cursor = db.cursor()
    rid = get_restaurante_id_or_403()
    
    cursor.execute("SELECT * FROM pedidos_delivery WHERE id = ? AND restaurante_id = ?", (pedido_id, rid))
    pedido = dict(cursor.fetchone())
    db.close()
    
    if not pedido:
        return jsonify({"sucesso": False, "erro": "Pedido não encontrado!"})
    
    itens = json.loads(pedido["itens"])
    
    mensagem = WhatsAppService.formatar_mensagem_pedido(pedido, itens)
    restaurante_id = pedido.get("restaurante_id") or rid
    numero = get_config("whatsapp_restaurante", Config.WHATSAPP_RESTAURANTE, restaurante_id=restaurante_id)
    link = WhatsAppService.gerar_link_whatsapp(mensagem, numero_destino=numero)
    
    return jsonify({
        "sucesso": True, 
        "link": link,
        "resumo": mensagem
    })

@app.route('/superadmin/pin', methods=['GET'])
def superadmin_pin():
    if session.get('role') not in ('superadmin', 'super_admin'):
        return redirect(url_for('auth.login_web'))
    if session.get('superadmin_pin_ok'):
        return redirect('/superadmin')
    return render_template('superadmin_pin.html', erro=None)


@app.route('/superadmin/pin', methods=['POST'])
@csrf.exempt
def superadmin_pin_post():
    if session.get('role') not in ('superadmin', 'super_admin'):
        return redirect(url_for('auth.login_web'))
    pin = request.form.get('pin', '').strip()
    if pin == SUPERADMIN_PIN:
        session['superadmin_pin_ok'] = True
        return redirect('/superadmin')
    return render_template('superadmin_pin.html', erro='PIN incorreto!')


@app.route("/superadmin")
@superadmin_required
def painel_superadmin():
    from datetime import date
    db = get_connection()
    cursor = db.cursor()
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN restaurante_id INT DEFAULT NULL")
        db.commit()
    except Exception:
        pass
    cursor.execute("""
        SELECT u.id, u.username, u.role, u.licenca_vencimento, r.slug, r.nome
        FROM restaurantes r
        JOIN users u ON u.restaurante_id = r.id AND u.role = 'admin'
        ORDER BY r.id
    """)
    admins = cursor.fetchall()
    db.close()
    clientes = []
    for a in admins:
        user_id, username, role, vencimento, slug, nome_restaurante = a
        if vencimento:
            venc_date = vencimento if isinstance(vencimento, date) else date.fromisoformat(str(vencimento))
            dias_restantes = (venc_date - date.today()).days
        else:
            venc_date = None
            dias_restantes = None
        clientes.append({
            "id": user_id,
            "username": username,
            "role": role,
            "vencimento": str(venc_date) if venc_date else None,
            "dias_restantes": dias_restantes,
            "slug": slug,
            "nome_restaurante": nome_restaurante
        })
    return render_template("superadmin.html", clientes=clientes)


@app.route("/superadmin/renovar/<int:user_id>/<int:dias>", methods=["POST"])
@csrf.exempt
@superadmin_required
def superadmin_renovar(user_id, dias):
    repo = UserRepository()
    repo.renovar_licenca(user_id, dias)
    return jsonify({"sucesso": True})


@app.route("/superadmin/bloquear/<int:user_id>", methods=["POST"])
@csrf.exempt
@superadmin_required
def superadmin_bloquear(user_id):
    repo = UserRepository()
    repo.bloquear_licenca(user_id)
    return jsonify({"sucesso": True})


@app.route("/superadmin/criar-restaurante", methods=["POST"])
@csrf.exempt
@superadmin_required
def superadmin_criar_restaurante():
    import unicodedata, re
    data = request.get_json()
    nome = (data.get('nome') or '').strip()
    username = (data.get('username') or '').strip()
    senha = (data.get('senha') or '').strip()

    if not nome or not username or not senha:
        return jsonify({"sucesso": False, "erro": "Preencha todos os campos."}), 400

    slug = unicodedata.normalize('NFD', nome)
    slug = ''.join(c for c in slug if unicodedata.category(c) != 'Mn')
    slug = slug.lower()
    slug = re.sub(r'[^a-z0-9\s-]', '', slug)
    slug = re.sub(r'\s+', '-', slug.strip())
    slug = re.sub(r'-+', '-', slug)

    db = get_connection()
    cursor = db.cursor()

    try:
        cursor.execute("ALTER TABLE users ADD COLUMN restaurante_id INT DEFAULT NULL")
        db.commit()
    except Exception:
        pass

    cursor.execute("SELECT id FROM restaurantes WHERE slug = %s", (slug,))
    if cursor.fetchone():
        db.close()
        return jsonify({"sucesso": False, "erro": f"Slug '{slug}' já está em uso."}), 409

    cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
    if cursor.fetchone():
        db.close()
        return jsonify({"sucesso": False, "erro": f"Usuário '{username}' já existe."}), 409

    cursor.execute(
        "INSERT INTO restaurantes (slug, nome, ativo) VALUES (%s, %s, 1)",
        (slug, nome)
    )
    db.commit()
    restaurante_id = cursor.lastrowid

    password_hash = SecurityService.hash_password(senha)
    cursor.execute(
        "INSERT INTO users (username, password_hash, role, restaurante_id) VALUES (%s, %s, 'admin', %s)",
        (username, password_hash, restaurante_id)
    )
    db.commit()
    db.close()

    return jsonify({"sucesso": True, "slug": slug, "url": f"/cardapio/{slug}"})


@app.route("/admin/toggle-status", methods=["POST"])
@admin_required
def admin_toggle_status():
    """Toggle rápido para abrir/fechar o estabelecimento."""
    rid = get_restaurante_id_or_403()
    atual = get_config("restaurante_ativo", "1", restaurante_id=rid)
    novo = "0" if atual == "1" else "1"
    set_config("restaurante_ativo", novo, restaurante_id=rid)
    _ultima_verificacao_status.pop(f"status_{rid}", None)
    return jsonify({"restaurante_ativo": novo})


@app.route("/admin/configuracoes", methods=["GET", "POST"])
@admin_required
def admin_configuracoes():
    sucesso = None
    erro = None
    rid = get_restaurante_id_or_403()
    if request.method == "POST":
        campos = [
            "nome_restaurante", "whatsapp_restaurante",
            "frete_por_km", "endereco_restaurante",
            "horario_abertura", "horario_fechamento",
            "cor_primaria"
        ]
        for campo in campos:
            valor = request.form.get(campo, "").strip()
            if valor != "":
                set_config(campo, valor, restaurante_id=rid)

        endereco = request.form.get("endereco_restaurante", "").strip()
        print("DEBUG endereco recebido:", repr(endereco))
        if endereco:
            try:
                import requests as req
                google_key = Config.GOOGLE_MAPS_KEY
                geo_url = "https://maps.googleapis.com/maps/api/geocode/json"
                geo_resp = req.get(geo_url, params={"address": endereco, "key": google_key})
                geo_data = geo_resp.json()
                print("DEBUG geocodificacao endereco:", endereco)
                print("DEBUG geo_data status:", geo_data.get("status"))
                if geo_data["status"] == "OK":
                    location = geo_data["results"][0]["geometry"]["location"]
                    lat = location["lat"]
                    lng = location["lng"]
                    print("DEBUG lat/lng:", lat, lng)
                    set_config("restaurante_lat", str(lat),
                              restaurante_id=rid)
                    set_config("restaurante_lng", str(lng),
                              restaurante_id=rid)
                else:
                    print("DEBUG geocodificacao ERRO status:", geo_data.get("status"), geo_data)
            except Exception as e:
                print("DEBUG geocodificacao EXCEPTION:", e)
                import traceback
                traceback.print_exc()

        dias = request.form.getlist('dias_funcionamento')
        dias_str = formatar_dias(dias)
        set_config("dias_funcionamento", dias_str, restaurante_id=rid)

        _ultima_verificacao_status.pop(f"status_{rid}", None)
        sucesso = "Configurações salvas com sucesso!"

    configs = {
        "nome_restaurante": get_config("nome_restaurante", "", restaurante_id=rid),
        "whatsapp_restaurante": get_config("whatsapp_restaurante", Config.WHATSAPP_RESTAURANTE, restaurante_id=rid),
        "frete_por_km": get_config("frete_por_km", str(Config.FRETE_POR_KM), restaurante_id=rid),
        "restaurante_lat": get_config("restaurante_lat", str(Config.RESTAURANTE_LAT), restaurante_id=rid),
        "restaurante_lng": get_config("restaurante_lng", str(Config.RESTAURANTE_LNG), restaurante_id=rid),
        "horario_abertura": get_config("horario_abertura", "18:00", restaurante_id=rid),
        "horario_fechamento": get_config("horario_fechamento", "23:00", restaurante_id=rid),
        "google_maps_key": Config.GOOGLE_MAPS_KEY,
        "restaurante_ativo": get_config("restaurante_ativo", "1", restaurante_id=rid),
        "endereco_restaurante": get_config("endereco_restaurante", "", restaurante_id=rid),
        "dias_funcionamento": get_config("dias_funcionamento", "", restaurante_id=rid),
        "dias_selecionados": parsear_dias(get_config("dias_funcionamento", "", restaurante_id=rid)),
    }

    configs["status_real"] = get_status_restaurante(rid)

    return render_template("admin_configuracoes.html", configs=configs, sucesso=sucesso, erro=erro)


# ========================
# ROTAS DO PAINEL DELIVERY
# ========================

@app.route("/api/novos-pedidos")
@login_required
def api_novos_pedidos():
    restaurante_id = get_restaurante_id_or_403()
    db = get_connection()
    cursor = db.cursor()
    ph = "%s" if is_mysql() else "?"
    cursor.execute(
        f"SELECT COUNT(*) FROM pedidos_delivery WHERE restaurante_id = {ph} AND status = 'novo'",
        (restaurante_id,)
    )
    total = cursor.fetchone()[0]
    db.close()
    return jsonify({"pendentes": total})


# ========== IMPRESSÃO DE COMANDA ==========

@app.route('/pedido/<int:id>/imprimir')
@login_required
def imprimir_pedido(id):
    db = get_connection()
    cursor = db.cursor()
    rid = get_restaurante_id_or_403()
    cursor.execute(
        "SELECT id, cliente_nome, cliente_telefone, cliente_endereco, itens, taxa_entrega, total, forma_pagamento, troco, status, criado_em FROM pedidos_delivery WHERE id = ? AND restaurante_id = ?",
        (id, rid)
    )
    pedido = cursor.fetchone()
    db.close()

    if not pedido:
        return "Pedido não encontrado", 404

    itens = json.loads(pedido[4]) if pedido[4] else []

    tipo = "retirada" if not pedido[3] or pedido[3].strip().lower() in ["retirada no local", "retirada", "balcao", "balcão"] else "delivery"

    return render_template('imprimir_pedido.html',
        pedido_id=pedido[0],
        cliente_nome=pedido[1],
        cliente_telefone=pedido[2],
        cliente_endereco=pedido[3],
        itens=itens,
        taxa_entrega=pedido[5],
        total=pedido[6],
        forma_pagamento=pedido[7],
        troco=pedido[8],
        status=pedido[9],
        criado_em=pedido[10],
        nome_restaurante=get_config("nome_restaurante", "Comanda Digital"),
        tipo_pedido=tipo,
    )


@app.route('/delivery/imprimir/<int:id>')
@login_required
def delivery_imprimir(id):
    db = get_connection()
    cursor = db.cursor()
    rid = get_restaurante_id_or_403()
    cursor.execute(
        "SELECT id, cliente_nome, cliente_telefone, cliente_endereco, itens, taxa_entrega, total, forma_pagamento, troco, status, criado_em FROM pedidos_delivery WHERE id = ? AND restaurante_id = ?",
        (id, rid)
    )
    pedido = cursor.fetchone()
    db.close()

    if not pedido:
        return "Pedido não encontrado", 404

    itens = json.loads(pedido[4]) if pedido[4] else []

    tipo = "retirada" if not pedido[3] or pedido[3].strip().lower() in ["retirada no local", "retirada", "balcao", "balcão"] else "delivery"

    return render_template('imprimir_pedido.html',
        pedido_id=pedido[0],
        cliente_nome=pedido[1],
        cliente_telefone=pedido[2],
        cliente_endereco=pedido[3],
        itens=itens,
        taxa_entrega=pedido[5],
        total=pedido[6],
        forma_pagamento=pedido[7],
        troco=pedido[8],
        status=pedido[9],
        criado_em=pedido[10],
        nome_restaurante=get_config("nome_restaurante", "Comanda Digital"),
        tipo_pedido=tipo,
    )


@app.route('/api/imprimir/<int:pedido_id>', methods=["POST"])
@csrf.exempt
@login_required
def api_imprimir_escpos(pedido_id):
    """Imprime comanda em impressora térmica via ESC/POS"""
    restaurante_id = get_restaurante_id_or_403()

    from services.impressao_service import imprimir_comanda

    try:
        imprimir_comanda(pedido_id=pedido_id, restaurante_id=restaurante_id)
        return jsonify({"sucesso": True, "mensagem": "Impressão enviada com sucesso!"})
    except ValueError as e:
        return jsonify({"sucesso": False, "erro": str(e)}), 404
    except ConnectionError as e:
        return jsonify({"sucesso": False, "erro": str(e)}), 502
    except Exception as e:
        logger.error(f"Erro ao imprimir pedido #{pedido_id}: {e}")
        return jsonify({"sucesso": False, "erro": "Erro inesperado ao imprimir."}), 500


# ========== MIGRAÇÃO DO BANCO ==========

@app.route('/admin/migrar-banco')
@login_required
def migrar_banco():
    """Adiciona colunas faltantes ao banco sem perder dados existentes."""
    if session.get('role') not in ('admin', 'superadmin', 'super_admin'):
        return redirect(url_for('mesas.mesas'))
    db = get_connection()
    cursor = db.cursor()
    resultados = []

    migracoes = [
        ("pedidos_delivery", "forma_pagamento", "VARCHAR(50) DEFAULT NULL"),
        ("pedidos_delivery", "troco",           "DOUBLE DEFAULT 0"),
    ]

    for tabela, coluna, definicao in migracoes:
        try:
            cursor.execute(f"SHOW COLUMNS FROM {tabela} LIKE '{coluna}'")
            existe = cursor.fetchone()
            if existe:
                cursor.execute(f"ALTER TABLE {tabela} MODIFY {coluna} {definicao}")
                db.commit()
                resultados.append(f"CORRIGIDO: '{coluna}' em '{tabela}' → {definicao}")
            else:
                cursor.execute(f"ALTER TABLE {tabela} ADD COLUMN {coluna} {definicao}")
                db.commit()
                resultados.append(f"OK: coluna '{coluna}' adicionada em '{tabela}'")
        except Exception as e:
            resultados.append(f"ERRO em '{tabela}.{coluna}': {e}")

    db.close()
    return "<br>".join(resultados) + "<br><br><a href='/admin'>Voltar ao painel</a>"


# ========== ADMIN PRODUTOS ==========

@app.route('/admin/produtos')
@admin_required
def admin_produtos():
    produtos = listar_produtos(get_restaurante_id_or_403())
    return render_template('admin_produtos.html', produtos=produtos)

@app.route('/admin/produtos/adicionar', methods=['POST'])
@admin_required
def adicionar_produto_route():
    nome = request.form['nome']
    preco = float(request.form['preco'])
    categoria = request.form['categoria']
    emoji = request.form.get('emoji', '')
    foto = None

    if 'foto' in request.files:
        arquivo = request.files['foto']
        if arquivo.filename != '':
            if not extensao_valida(arquivo.filename):
                return redirect('/admin/produtos')
            nome_seguro = secure_filename(arquivo.filename)
            caminho_salvar = os.path.join(UPLOAD_FOLDER, nome_seguro)
            img = Image.open(arquivo)
            img.thumbnail((800, 800))
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            img.save(caminho_salvar, optimize=True, quality=75)
            foto = os.path.join('uploads', 'produtos', nome_seguro)

    descricao = request.form.get('descricao', '').strip() or None
    adicionar_produto(nome, preco, categoria, emoji, get_restaurante_id_or_403(), foto, descricao)
    return redirect('/admin/produtos')

@app.route('/admin/produtos/editar/<int:id>', methods=['POST'])
@admin_required
def editar_produto_route(id):
    nome = request.form['nome']
    preco = float(request.form['preco'])
    categoria = request.form['categoria']
    emoji = request.form['emoji']
    foto = None

    if 'foto' in request.files:
        arquivo = request.files['foto']
        if arquivo.filename != '':
            if not extensao_valida(arquivo.filename):
                return redirect('/admin/produtos')
            nome_seguro = secure_filename(arquivo.filename)
            caminho_salvar = os.path.join(UPLOAD_FOLDER, nome_seguro)
            arquivo.save(caminho_salvar)
            foto = os.path.join('uploads', 'produtos', nome_seguro)

    editar_produto(id, nome, preco, categoria, emoji, get_restaurante_id_or_403(), foto)
    return redirect('/admin/produtos')

@app.route('/admin/produtos/desativar/<int:id>')
@admin_required
def desativar_produto_route(id):
    desativar_produto(id, get_restaurante_id_or_403())
    return redirect('/admin/produtos')



@app.route('/admin/alterar-senha', methods=['GET', 'POST'])
@admin_required
def alterar_senha():
    erro = None
    sucesso = None
    if request.method == 'POST':
        senha_atual = request.form.get('senha_atual', '')
        nova_senha  = request.form.get('nova_senha', '')
        confirmar   = request.form.get('confirmar', '')

        repo = UserRepository()
        user = repo.get_user_by_username(session['username'])

        if not SecurityService.verify_password(senha_atual, user.password_hash):
            erro = 'Senha atual incorreta.'
        elif len(nova_senha) < 6:
            erro = 'A nova senha deve ter pelo menos 6 caracteres.'
        elif nova_senha != confirmar:
            erro = 'As senhas não coincidem.'
        else:
            repo.update_password(user.id, nova_senha)
            sucesso = 'Senha alterada com sucesso!'

    return render_template('alterar_senha.html', erro=erro, sucesso=sucesso)

# ========== GERENCIAR USUÁRIOS ==========

@app.route('/admin/usuarios', methods=['GET', 'POST'])
@admin_required
def gerenciar_usuarios():
    repo = UserRepository()
    erro = None
    sucesso = None

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        confirmar = request.form.get('confirmar', '')

        role = request.form.get('role', 'atendente')
        if role not in ('garcom', 'atendente', 'caixa'):
            role = 'atendente'

        if not username or not password:
            erro = 'Preencha usuário e senha.'
        elif len(password) < 6:
            erro = 'A senha deve ter pelo menos 6 caracteres.'
        elif password != confirmar:
            erro = 'As senhas não coincidem.'
        elif not repo.create_custom_admin(username, password, get_restaurante_id_or_403(), role):
            erro = f'O usuário "{username}" já existe.'
        else:
            sucesso = f'Usuário "{username}" criado com sucesso!'

    usuarios = repo.list_users(get_restaurante_id_or_403())
    return render_template('admin_usuarios.html', usuarios=usuarios, erro=erro, sucesso=sucesso)

@app.route('/admin/usuarios/remover/<int:user_id>', methods=['POST'])   
@admin_required
def remover_usuario(user_id):
    repo = UserRepository()
    repo.delete_user(user_id, session['user_id'], get_restaurante_id_or_403())
    return redirect('/admin/usuarios')





@app.route("/api/caixa/grafico")
@caixa_or_admin_required
def caixa_grafico():
    """Retorna faturamento agrupado por hora para gráfico"""
    try:
        db = get_connection()
        if not is_mysql():
            import sqlite3
            db.row_factory = sqlite3.Row
        else:
            db.row_factory = True
        cursor = db.cursor()
        rid = get_restaurante_id_or_403()

        sessao_inicio = _get_sessao_inicio(cursor, rid)
        horas = {h: 0.0 for h in range(24)}

        def obter_valor(row, key, idx):
            if isinstance(row, dict): return row.get(key)
            return row[idx] if row and len(row) > idx else None

        cursor.execute("""
            SELECT CAST(strftime('%H', criado_em, 'localtime') AS INTEGER) as hora,
                   COALESCE(SUM(total), 0) as total
            FROM pedidos_delivery
            WHERE criado_em >= ?
            AND status = 'entregue'
            AND restaurante_id = ?
            GROUP BY hora
        """, (sessao_inicio, rid))
        for row in cursor.fetchall():
            h = obter_valor(row, 'hora', 0)
            if h is not None:
                horas[int(h)] += float(obter_valor(row, 'total', 1))

        cursor.execute("""
            SELECT CAST(strftime('%H', fechado_em, 'localtime') AS INTEGER) as hora,
                   COALESCE(SUM(total), 0) as total
            FROM historico_mesas
            WHERE fechado_em >= ?
            AND restaurante_id = ?
            GROUP BY hora
        """, (sessao_inicio, rid))
        for row in cursor.fetchall():
            h = obter_valor(row, 'hora', 0)
            if h is not None:
                horas[int(h)] += float(obter_valor(row, 'total', 1))

        cursor.execute("""
            SELECT CAST(strftime('%H', fechado_em, 'localtime') AS INTEGER) as hora,
                   COALESCE(SUM(total), 0) as total
            FROM historico_mesas
            WHERE fechado_em >= ?
            AND restaurante_id = ?
            GROUP BY hora
        """, (sessao_inicio, rid))
        for row in cursor.fetchall():
            h = get_val(row, 'hora', 0)
            if h is not None:
                horas[int(h)] += float(get_val(row, 'total', 1))

        return jsonify({
            "sucesso": True,
            "horas": [{"hora": h, "total": horas[h]} for h in sorted(horas.keys())]
        })
    except Exception as e:
        import traceback
        msg_erro = traceback.format_exc()
        with open("caixa_error.log", "a", encoding="utf-8") as f:
            f.write(f"\n--- [GRAFICO] {datetime.now()} ---\n{msg_erro}\n")
        print(f"Erro em /api/caixa/grafico:\n{msg_erro}")
        return jsonify({"sucesso": False, "erro": str(e)}), 200

# ========== GOOGLE MAPS / FRETE ==========

@app.route("/api/maps/config")
@csrf.exempt
@limiter.limit("120/minute")
def maps_config():
    """Retorna configuração do Google Maps para o frontend"""
    return jsonify({
        "sucesso": True,
        "api_key": Config.GOOGLE_MAPS_KEY,
        "restaurante_lat": Config.RESTAURANTE_LAT,
        "restaurante_lng": Config.RESTAURANTE_LNG,
        "frete_por_km": Config.FRETE_POR_KM
    })


@app.route("/carrinho")
@limiter.limit("120/minute")
def carrinho_cliente():
    try:
        db = get_connection()
        cursor = db.cursor()
        cursor.execute("SELECT id FROM restaurantes WHERE ativo = 1 ORDER BY id LIMIT 1")
        row = cursor.fetchone()
        rid = row[0] if row else 1
        db.close()
    except Exception:
        rid = 1
    return render_template("carrinho_cliente.html", slug=None, restaurante_id=rid, google_maps_key=Config.GOOGLE_MAPS_KEY)


# ========================
# ROTAS MULTI-TENANT
# ========================


@app.route("/cardapio/<slug>/api/cardapio")
@limiter.limit("120/minute")
def api_cardapio_por_slug(slug):
    from data.db import get_connection
    db = get_connection()
    cursor = db.cursor()
    cursor.execute("SELECT id FROM restaurantes WHERE slug = %s AND ativo = 1", (slug,))
    row = cursor.fetchone()
    if not row:
        db.close()
        return jsonify({"sucesso": False, "erro": "Restaurante não encontrado"}), 404
    restaurante_id = row[0]
    cursor.execute("""
        SELECT id, nome, preco, categoria, emoji, ativo, foto, descricao
        FROM produtos WHERE restaurante_id = %s AND ativo = 1
    """, (restaurante_id,))
    produtos = cursor.fetchall()
    db.close()
    resultado = []
    for p in produtos:
        resultado.append({
            "id": p[0],
            "nome": p[1],
            "preco": p[2],
            "categoria": p[3],
            "emoji": p[4],
            "foto": p[6] if len(p) > 6 else None,
            "descricao": p[7] if len(p) > 7 else ""
        })
    return jsonify({"sucesso": True, "produtos": resultado})

@app.route("/cardapio/<slug>/api/adicionais")
@limiter.limit("120/minute")
def api_adicionais_por_slug(slug):
    from data.db import get_connection
    db = get_connection()
    cursor = db.cursor()
    cursor.execute("SELECT id FROM restaurantes WHERE slug = %s AND ativo = 1", (slug,))
    row = cursor.fetchone()
    if not row:
        db.close()
        return jsonify({"sucesso": False, "erro": "Restaurante não encontrado"}), 404
    restaurante_id = row[0]
    categoria = request.args.get('categoria', None)
    if categoria:
        cursor.execute("""
            SELECT a.id, a.nome, a.preco FROM adicionais a
            JOIN adicional_categoria ac ON a.id = ac.adicional_id
            WHERE a.restaurante_id = %s AND a.ativo = 1 AND ac.categoria = %s
        """, (restaurante_id, categoria))
    else:
        cursor.execute("""
            SELECT id, nome, preco FROM adicionais
            WHERE restaurante_id = %s AND ativo = 1
        """, (restaurante_id,))
    adicionais = cursor.fetchall()
    db.close()
    resultado = [{"id": a[0], "nome": a[1], "preco": a[2]} for a in adicionais]
    return jsonify({"sucesso": True, "adicionais": resultado})

@app.route("/cardapio/<slug>/carrinho")
@limiter.limit("120/minute")
def carrinho_por_slug(slug):
    from data.db import get_connection
    db = get_connection()
    cursor = db.cursor()
    cursor.execute("SELECT id FROM restaurantes WHERE slug = %s AND ativo = 1", (slug,))
    row = cursor.fetchone()
    db.close()
    if not row:
        abort(404)
    restaurante_id = row[0]
    google_maps_key = os.getenv('GOOGLE_MAPS_API_KEY', '')
    return render_template("carrinho_cliente.html", slug=slug, restaurante_id=restaurante_id, google_maps_key=os.getenv('GOOGLE_MAPS_API_KEY', ''))

@app.route("/cardapio/<slug>/api/pedido", methods=["POST"])
@csrf.exempt
@limiter.limit("30/minute")
def criar_pedido_por_slug(slug):
    from data.db import get_connection
    db = get_connection()
    cursor = db.cursor()
    cursor.execute("SELECT id FROM restaurantes WHERE slug = %s AND ativo = 1", (slug,))
    row = cursor.fetchone()
    if not row:
        db.close()
        return jsonify({"sucesso": False, "erro": "Restaurante não encontrado"}), 404
    restaurante_id = row[0]
    db.close()
    # Reutiliza a lógica existente de criar_pedido injetando restaurante_id
    dados = request.get_json()
    dados['restaurante_id'] = restaurante_id
    request._cached_json = (dados, dados)
    return route_criar_pedido()

@app.route("/api/restaurante/<slug>")
@limiter.limit("120/minute")
def api_restaurante_por_slug(slug):
    from data.db import get_connection

    db = get_connection()
    cursor = db.cursor()
    cursor.execute("SELECT id, nome, ativo FROM restaurantes WHERE slug = %s", (slug,))
    row = cursor.fetchone()
    db.close()

    if not row:
        return jsonify({"sucesso": False, "erro": "Restaurante não encontrado"}), 404

    restaurante_id, nome, ativo_db = row[0], row[1], row[2]

    if not ativo_db:
        status = "fechado"
    else:
        status = get_status_restaurante(restaurante_id)

    horario_abertura = get_config("horario_abertura", "18:00", restaurante_id)
    horario_fechamento = get_config("horario_fechamento", "23:00", restaurante_id)
    dias_funcionamento = get_config("dias_funcionamento", "", restaurante_id)

    base_url = request.host_url.rstrip('/')
    link_cardapio = f"{base_url}/cardapio/{slug}"

    return jsonify({
        "nome": nome,
        "slug": slug,
        "horario_abertura": horario_abertura,
        "horario_fechamento": horario_fechamento,
        "dias_funcionamento": dias_funcionamento,
        "status": status,
        "link_cardapio": link_cardapio,
    })


@app.route("/api/check-status/<string:slug>")
@limiter.limit("120/minute")
def api_check_status(slug):
    from data.db import get_connection
    restaurante_id = _get_rid_from_slug(slug)
    if not restaurante_id:
        return jsonify({"sucesso": False, "erro": "slug invalido"}), 400
    verificar_horario_funcionamento(restaurante_id)
    db = get_connection()
    cursor = db.cursor()
    if is_mysql():
        cursor.execute("SELECT status FROM restaurantes WHERE id = %s", (restaurante_id,))
    else:
        cursor.execute("SELECT status FROM restaurantes WHERE id = ?", (restaurante_id,))
    row = cursor.fetchone()
    db.close()
    status = row[0] if row else "fechado"
    return jsonify({"status": status})


@app.route('/admin/adicionais')
@admin_required
def admin_adicionais():
    rid = get_restaurante_id_or_403()
    adicionais = listar_adicionais_com_categorias(rid)
    categorias = listar_categorias_produtos(rid)
    return render_template('admin_adicionais.html', adicionais=adicionais, categorias=categorias)

@app.route('/admin/adicionais/adicionar', methods=['POST'])
@admin_required
def adicionar_adicional_route():
    nome = request.form['nome'].strip()
    preco = float(request.form['preco'])
    categorias = request.form.getlist('categorias')
    if nome and preco >= 0 and categorias:
        adicionar_adicional(nome, preco, categorias, get_restaurante_id_or_403())
    return redirect('/admin/adicionais')

@app.route('/admin/adicionais/editar/<int:id>', methods=['POST'])
@admin_required
def editar_adicional_route(id):
    nome = request.form['nome'].strip()
    preco = float(request.form['preco'])
    categorias = request.form.getlist('categorias')
    editar_adicional(id, nome, preco, categorias, get_restaurante_id_or_403())
    return redirect('/admin/adicionais')

@app.route('/admin/adicionais/desativar/<int:id>', methods=['POST'])
@admin_required
def desativar_adicional_route(id):
    desativar_adicional(id, get_restaurante_id_or_403())
    return redirect('/admin/adicionais')

@app.route('/admin/adicionais/excluir/<int:id>', methods=['POST'])
@admin_required
def excluir_adicional_route(id):
    excluir_adicional(id, get_restaurante_id_or_403())
    return jsonify({"sucesso": True})

@app.route('/api/categorias')
@limiter.limit("120/minute")
def api_categorias():
    categorias = listar_categorias_produtos(get_restaurante_id_or_403())
    return jsonify({"sucesso": True, "categorias": categorias})


@app.route("/admin/categorias")
@admin_required
def admin_categorias():
    categorias = listar_categorias_produtos(get_restaurante_id_or_403())
    return render_template("admin_categorias.html", categorias=categorias)


@app.route("/pdv")
@login_required
def pdv():
    """Página do PDV (Ponto de Venda)"""
    return render_template("admin_pdv.html")


# ========================
# CACHE DE CLIENTES
# ========================

@app.route("/api/cliente/<telefone>")
@csrf.exempt
@limiter.limit("120/minute")
def get_cliente(telefone):
    slug = request.args.get('slug', '').strip()
    restaurante_id = _get_rid_from_slug(slug)
    if not restaurante_id:
        return jsonify({"sucesso": False, "erro": "slug invalido ou ausente"}), 400
    db = get_connection()
    cursor = db.cursor()
    cursor.execute(
        "SELECT nome, endereco FROM clientes_cache WHERE telefone = ? AND restaurante_id = ?",
        (telefone, restaurante_id)
    )
    row = cursor.fetchone()
    db.close()
    if row:
        return jsonify({"sucesso": True, "nome": row[0], "endereco": row[1]})
    return jsonify({"sucesso": False})


@app.route("/api/cliente", methods=["POST"])
@csrf.exempt
@limiter.limit("30/minute")
def salvar_cliente():
    dados = request.get_json()
    telefone = dados.get("telefone", "").strip()
    nome = dados.get("nome", "").strip()
    endereco = dados.get("endereco", "").strip()
    slug = (dados.get("slug") or "").strip()
    restaurante_id = _get_rid_from_slug(slug)
    if not telefone:
        return jsonify({"sucesso": False})
    if not restaurante_id:
        return jsonify({"sucesso": False, "erro": "slug invalido ou ausente"}), 400
    db = get_connection()
    cursor = db.cursor()
    if is_mysql():
        cursor.execute("""
            INSERT INTO clientes_cache (telefone, nome, endereco, restaurante_id)
            VALUES (%s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE nome=%s, endereco=%s
        """, (telefone, nome, endereco, restaurante_id, nome, endereco))
    else:
        cursor.execute("""
            INSERT INTO clientes_cache (telefone, nome, endereco, restaurante_id)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(telefone, restaurante_id) DO UPDATE SET nome=excluded.nome, endereco=excluded.endereco
        """, (telefone, nome, endereco, restaurante_id))
    db.commit()
    db.close()
    return jsonify({"sucesso": True})



@app.route("/debug/proxy")
@admin_required
def debug_proxy():
    if not app.debug and not os.environ.get("DEBUG_PROXY"):
        return jsonify({"erro": "rota apenas em debug"}), 403
    return jsonify({
        "is_secure": request.is_secure,
        "scheme": request.scheme,
        "x_forwarded_proto": request.headers.get("X-Forwarded-Proto"),
        "x_forwarded_for": request.headers.get("X-Forwarded-For"),
        "host": request.headers.get("Host"),
        "cookie_secure_config": {
            "SESSION_COOKIE_SECURE": app.config.get("SESSION_COOKIE_SECURE"),
            "session_cookie_secure_talisman": False,
        }
    })

if __name__ == "__main__":
    repo = UserRepository()
    repo.init_user_table()
    if not repo.has_any_user():
        print("⚙️  Primeiro acesso! Configure o admin em: http://127.0.0.1:5000/setup")
    else:
        print("✅ Sistema pronto! Acesse http://127.0.0.1:5000/login")
    print("🔐 Login obrigatório para acessar o sistema!")
    print("=" * 50)

    app.run(debug=False, port=int(os.environ.get('PORT', 5000)), host='0.0.0.0')
