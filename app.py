import json
from datetime import datetime
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
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_talisman import Talisman
from PIL import Image
import io
def inicializar_admin():
    from repository import UserRepository
    from security import SecurityService
    repo = UserRepository()
    user = repo.get_user_by_username(Config.ADMIN_USER)
    if not user:
        repo.create_admin()
        print(f"Admin '{Config.ADMIN_USER}' criado automaticamente.")

#inicializar_admin()

# Logging de segurança
logging.basicConfig(level=logging.WARNING,
                    format='%(asctime)s - %(levelname)s - %(message)s')

app = Flask(__name__)
from werkzeug.middleware.proxy_fix import ProxyFix
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

app.secret_key = Config.SECRET_KEY

# Proteção CSRF
csrf = CSRFProtect(app)

# Rate limiting
limiter = Limiter(get_remote_address, app=app, default_limits=[])

# Headers de segurança
Talisman(app,
    force_https=False,
    content_security_policy={
        'default-src': "'self'",
        'script-src': "'self' 'unsafe-inline' maps.googleapis.com",
        'style-src': "'self' 'unsafe-inline' fonts.googleapis.com",
        'img-src': "'self' data: maps.gstatic.com *.googleapis.com *.gstatic.com",
        'font-src': "'self' data: fonts.gstatic.com",
        'connect-src': "'self' maps.googleapis.com *.googleapis.com",
    },
    session_cookie_secure=True, 
)

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
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    SESSION_COOKIE_SECURE=True,
    PERMANENT_SESSION_LIFETIME=28800
)
# Inicia o banco usando o db.py
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
        'login_web', 'logout', 'static',
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
                telefone VARCHAR(20) PRIMARY KEY,
                nome VARCHAR(100),
                endereco VARCHAR(255),
                atualizado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)
    else:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS clientes_cache (
                telefone TEXT PRIMARY KEY,
                nome TEXT,
                endereco TEXT,
                atualizado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
    db.commit()
    db.close()

_garantir_clientes_cache()


# NOVO — Tabela de configurações do estabelecimento
def _garantir_configuracoes():
    db = get_connection()
    cursor = db.cursor()
    if is_mysql():
        # Cria tabela com schema correto se não existir
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


# NOVO — Helpers de configuração
def get_config(chave, fallback=None, restaurante_id=1):
    """Lê uma configuração do banco. Usa fallback se não encontrar."""
    try:
        db = get_connection()
        cursor = db.cursor()
        if is_mysql():
            cursor.execute("SELECT valor FROM configuracoes WHERE chave = %s AND restaurante_id = %s", (chave, restaurante_id))
        else:
            cursor.execute("SELECT valor FROM configuracoes WHERE chave = ? AND restaurante_id = ?", (chave, restaurante_id))
        row = cursor.fetchone()
        db.close()
        if row:
            return row[0]
    except Exception:
        pass
    return fallback


def set_config(chave, valor, restaurante_id=1):
    """Salva ou atualiza uma configuração no banco."""
    db = get_connection()
    cursor = db.cursor()
    if is_mysql():
        cursor.execute("""
            INSERT INTO configuracoes (chave, valor, restaurante_id)
            VALUES (%s, %s, %s)
            ON DUPLICATE KEY UPDATE valor = %s, atualizado_em = CURRENT_TIMESTAMP
        """, (chave, valor, restaurante_id, valor))
    else:
        cursor.execute("""
            INSERT INTO configuracoes (chave, valor, restaurante_id) VALUES (?, ?, ?)
            ON CONFLICT(chave, restaurante_id) DO UPDATE SET valor = excluded.valor
        """, (chave, valor, restaurante_id))
    db.commit()
    db.close()


DIAS_ORDEM = ['Segunda', 'Terca', 'Quarta', 'Quinta', 'Sexta', 'Sabado', 'Domingo']

def formatar_dias(dias):
    if not dias:
        return ''
    selecionados = [d for d in DIAS_ORDEM if d in dias]
    if not selecionados:
        return ''
    if len(selecionados) == len(DIAS_ORDEM):
        return 'Todos os dias'
    indices = [DIAS_ORDEM.index(d) for d in selecionados]
    indices.sort()
    if len(indices) == indices[-1] - indices[0] + 1:
        return f"{selecionados[0]} a {selecionados[-1]}"
    return ', '.join(selecionados)

def parsear_dias(texto):
    if not texto:
        return []
    if texto == 'Todos os dias':
        return DIAS_ORDEM[:]
    if ' a ' in texto:
        partes = texto.split(' a ')
        if partes[0] in DIAS_ORDEM and partes[1] in DIAS_ORDEM:
            inicio = DIAS_ORDEM.index(partes[0])
            fim = DIAS_ORDEM.index(partes[1])
            return DIAS_ORDEM[inicio:fim+1]
    return [d.strip() for d in texto.split(',')]


_ultima_verificacao_status = {}

def verificar_horario_funcionamento(restaurant_id):
    from datetime import datetime

    agora_dt = datetime.now()
    chave = f"status_{restaurant_id}"
    ultima = _ultima_verificacao_status.get(chave)
    if ultima and (agora_dt - ultima).total_seconds() < 300:
        return

    try:
        horario_abertura = get_config("horario_abertura", "18:00", restaurante_id=restaurant_id)
        horario_fechamento = get_config("horario_fechamento", "23:00", restaurante_id=restaurant_id)
        dias_funcionamento = get_config("dias_funcionamento", "", restaurante_id=restaurant_id)
        restaurante_ativo = get_config("restaurante_ativo", "1", restaurante_id=restaurant_id)

        if restaurante_ativo == "0":
            novo_status = "fechado"
        else:
            try:
                import zoneinfo
                tz = zoneinfo.ZoneInfo("America/Sao_Paulo")
            except ImportError:
                from datetime import timezone, timedelta
                tz = timezone(timedelta(hours=-3))

            agora = datetime.now(tz)

            dias = parsear_dias(dias_funcionamento)

            mapa = {
                "Monday": "Segunda", "Tuesday": "Terca", "Wednesday": "Quarta",
                "Thursday": "Quinta", "Friday": "Sexta", "Saturday": "Sabado", "Sunday": "Domingo"
            }
            dia_atual = mapa.get(agora.strftime("%A"), "")

            if not dias or dia_atual not in dias:
                novo_status = "fechado"
            else:
                try:
                    abertura = datetime.strptime(horario_abertura, "%H:%M").time()
                    fechamento = datetime.strptime(horario_fechamento, "%H:%M").time()
                    hora_atual = agora.time()
                    novo_status = "aberto" if abertura <= hora_atual <= fechamento else "fechado"
                except Exception:
                    novo_status = "fechado"

        db = get_connection()
        cursor = db.cursor()
        if is_mysql():
            cursor.execute("UPDATE restaurantes SET status = %s WHERE id = %s", (novo_status, restaurant_id))
        else:
            cursor.execute("UPDATE restaurantes SET status = ? WHERE id = ?", (novo_status, restaurant_id))
        db.commit()
        db.close()

        _ultima_verificacao_status[chave] = datetime.now()
    except Exception:
        pass


def _get_sessao_inicio(cursor, restaurante_id=1):
    """Retorna o datetime de início da sessão atual do caixa como string."""
    cursor.execute("""
        SELECT aberto_em FROM caixa_sessoes
        WHERE DATE(aberto_em, 'localtime') = DATE('now', 'localtime')
        AND restaurante_id = ?
        ORDER BY aberto_em DESC LIMIT 1
    """, (restaurante_id,))
    row = cursor.fetchone()
    if row:
        try:
            aberto_em = row['aberto_em']
        except (TypeError, KeyError):
            aberto_em = row[0]
        if hasattr(aberto_em, 'strftime'):
            return aberto_em.strftime('%Y-%m-%d %H:%M:%S')
        return str(aberto_em)
    from datetime import datetime
    return datetime.now().strftime('%Y-%m-%d') + ' 00:00:00'


# ========================
# DECORATOR PARA PROTEGER ROTAS
# ========================
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login_web'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login_web'))
        if session.get('role') not in ('admin', 'superadmin', 'super_admin'):
            return redirect(url_for('mesas'))
        return f(*args, **kwargs)
    return decorated_function

# NOVO — decorator para rotas de caixa (admin + caixa + super)
def caixa_or_admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login_web'))
        if session.get('role') not in ('admin', 'superadmin', 'super_admin', 'caixa'):
            return redirect(url_for('mesas'))
        return f(*args, **kwargs)
    return decorated

# NOVO — decorator exclusivo do superadmin
def superadmin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get('role') not in ('superadmin', 'super_admin'):
            return redirect(url_for('login_web'))
        if not session.get('superadmin_pin_ok'):
            return redirect(url_for('superadmin_pin'))
        return f(*args, **kwargs)
    return decorated


# NOVO — verifica se o admin tem licença válida
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


# ROTAS DE AUTENTICAÇÃO

@app.route("/login", methods=['GET', 'POST'])
@csrf.exempt
@limiter.limit("5 per minute")
def login_web():
    if request.method == 'POST':
        username = request.form.get('username').strip()
        password = request.form.get('password').strip()
        
        repo = UserRepository()
        user = repo.get_user_by_username(username)
        logging.warning(f"[DEBUG] login_web user: {user}")
        if user:
            logging.warning(f"[DEBUG] login_web user.password_hash: {user.password_hash}")
        if user and SecurityService.verify_password(password, user.password_hash):
            session['user_id'] = user.id
            session['username'] = user.username
            session['role'] = user.role
            session['restaurante_id'] = user.restaurante_id
            return redirect(url_for('index'))
        else:
            logging.warning(f"Login falhou para '{username}' de {request.remote_addr}")
            return render_template('login.html', erro='Usuário ou senha inválidos!')
    
    return render_template('login.html')

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for('login_web'))

@app.route("/setup", methods=['GET', 'POST'])
def setup():
    """Configuração inicial — só acessível se não há usuários cadastrados"""
    repo = UserRepository()
    if repo.has_any_user():
        return redirect(url_for('login_web'))

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
            return redirect(url_for('login_web'))

    return render_template('setup.html', erro=erro)

# ========================
# ROTAS PRINCIPAIS
# ========================
@app.route('/')
def home():
    return render_template('landing.html')
@app.route("/dashboard")
@login_required
def index():
    role = session.get('role')
    restaurante_slug = None
    rid = session.get('restaurante_id') or 1
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
        return redirect(url_for('mesas'))
    elif role == 'caixa':
        return render_template('caixa.html')
    elif role in ('superadmin', 'super_admin'):
        return render_template('dashboard.html', restaurante_slug=restaurante_slug)
    else:
        return redirect(url_for('login_web'))


@app.route("/mesas")
@login_required
def mesas():
    """Página de gestão de mesas — design moderno com cards e status visual."""
    return render_template("admin_mesas.html")

@app.route("/api/dashboard/resumo")
@login_required
def dashboard_resumo():
    """Retorna contadores para o dashboard"""
    try:
        rid = session.get('restaurante_id', 1)
        resumo = obter_resumo_dashboard(rid)
        return jsonify({"sucesso": True, **resumo})
    except Exception as e:
        app.logger.error(f"Erro no dashboard_resumo: {e}")
        return jsonify({"sucesso": False, "erro": "Erro interno ao buscar resumo"}), 500

@app.route("/api/mesas")
@login_required
def listar_mesas():
    try:
        rid = session.get('restaurante_id', 1)
        mesas = listar_mesas_com_itens(rid)
        return jsonify({"sucesso": True, "mesas": mesas})
    except Exception as e:
        app.logger.error(f"Erro no listar_mesas: {e}")
        return jsonify({"sucesso": False, "erro": "Erro ao listar mesas"}), 500

@app.route("/api/mesa/abrir", methods=["POST"])
@csrf.exempt
@login_required
def route_abrir_mesa():
    try:
        dados = request.get_json()
        num = str(dados.get("numero"))
        rid = session.get('restaurante_id', 1)
        
        sucesso, erro = repo_abrir_mesa(num, rid)
        return jsonify({"sucesso": sucesso, "erro": erro})
    except Exception as e:
        app.logger.error(f"Erro no abrir_mesa: {e}")
        return jsonify({"sucesso": False, "erro": "Erro ao abrir mesa"}), 500

@app.route("/api/mesa/item", methods=["POST"])
@csrf.exempt
@login_required
def adicionar_item():
    try:
        dados = request.get_json()
        num = str(dados.get("numero"))
        rid = session.get('restaurante_id', 1)
        
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
        rid = session.get('restaurante_id', 1)
        
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
        rid = session.get('restaurante_id', 1)
        
        sucesso, erro = fechar_mesa_com_historico(num, rid)
        return jsonify({"sucesso": sucesso, "erro": erro})
    except Exception as e:
        app.logger.error(f"Erro no fechar_mesa: {e}")
        return jsonify({"sucesso": False, "erro": "Erro ao fechar mesa"}), 500

@app.route("/admin/force_close_mesa/<int:mesa_id>")
@login_required
def force_close_mesa(mesa_id):
    """Fecha forçado de mesa corrompida"""
    try:
        rid = session.get('restaurante_id', 1)
        db = get_connection()
        cursor = db.cursor()
        ph = "%s" if is_mysql() else "?"
        cursor.execute(f"DELETE FROM itens WHERE mesa_id = {ph} AND restaurante_id = {ph}", (mesa_id, rid))
        cursor.execute(f"DELETE FROM mesas WHERE id = {ph} AND restaurante_id = {ph}", (mesa_id, rid))
        db.commit()
        db.close()
        return jsonify({"sucesso": True})
    except Exception as e:
        app.logger.error(f"Erro no force_close_mesa: {e}")
        return jsonify({"sucesso": False, "erro": str(e)}), 500

@app.route("/api/mesa/pedir-conta/<int:mesa_id>", methods=["POST"])
@csrf.exempt
@login_required
def pedir_conta(mesa_id):
    """Pedir conta da mesa - qualquer perfil autenticado"""
    try:
        rid = session.get('restaurante_id', 1)
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
        rid = session.get('restaurante_id', 1)
        mesa = get_mesa(mesa_id, rid)
        if not mesa:
            return jsonify({"sucesso": False, "erro": "Mesa não encontrada"}), 404
        sucesso, erro = repo_fechar_mesa(mesa_id, rid)
        return jsonify({"sucesso": sucesso, "erro": erro})
    except Exception as e:
        app.logger.error(f"Erro no fechar_mesa_id: {e}")
        return jsonify({"sucesso": False, "erro": "Erro ao fechar mesa"}), 500


# ========================
# REMOVA OU COMENTE O LOGIN DO TERMINAL
# ========================
# def fazer_login(): ... (pode remover essa função)
#Rotas para cliente no app.py


# ========================
# ROTAS PARA CLIENTES (DELIVERY)
# ========================

@app.route("/cardapio")
def cardapio_cliente():
    """Página do cardápio para clientes"""
    try:
        db = get_connection()
        cursor = db.cursor()
        cursor.execute("SELECT id FROM restaurantes WHERE ativo = 1 ORDER BY id LIMIT 1")
        row = cursor.fetchone()
        rid = row[0] if row else 1
        db.close()
    except Exception:
        rid = 1
    verificar_horario_funcionamento(rid)
    if get_config("restaurante_ativo", "1", restaurante_id=rid) == "0":
        return render_template("restaurante_inativo.html")
    return render_template("cardapio_cliente.html",
        slug=None,
        restaurante_nome=get_config('nome_restaurante', 'Restaurante', rid),
        restaurante_id=rid,
        whatsapp_restaurante=get_config('whatsapp_restaurante', Config.WHATSAPP_RESTAURANTE, rid),
        google_maps_key=Config.GOOGLE_MAPS_KEY)
@app.route("/api/cardapio")
def api_cardapio():
    """Retorna os produtos do cardápio"""
    try:
        rid = request.args.get('restaurante_id', 1)
        produtos = listar_produtos(rid)
        resultado = []
        for p in produtos:
            resultado.append({
                "id": p[0],
                "nome": p[1],
                "preco": float(p[2]),
                "categoria": p[3],
                "emoji": p[4] if p[4] else '🍽️',
                "foto": p[5],
                "descricao": p[6] if p[6] else "",    
            })
        return jsonify({"sucesso": True, "produtos": resultado})
    except Exception as e:
        app.logger.error(f"Erro no api_cardapio: {e}")
        return jsonify({"sucesso": False, "erro": "Erro ao carregar cardápio"}), 500

@app.route("/api/adicionais")
def api_adicionais():
    try:
        rid = request.args.get('restaurante_id', 1)
        categoria = request.args.get('categoria', None)
        adicionais = listar_adicionais(rid, categoria=categoria)
        resultado = [{"id": a[0], "nome": a[1], "preco": float(a[2])} for a in adicionais]
        return jsonify({"sucesso": True, "adicionais": resultado})
    except Exception as e:
        app.logger.error(f"Erro no api_adicionais: {e}")
        return jsonify({"sucesso": False, "erro": "Erro ao carregar adicionais"}), 500

@app.route("/api/pedido", methods=["POST"])
@csrf.exempt
def route_criar_pedido():
    """Cria um novo pedido delivery"""
    try:
        dados = request.get_json()
        resultado = criar_pedido_delivery(dados)
        
        # Gera resumo para o WhatsApp
        resumo = gerar_resumo_pedido(
            resultado["pedido_id"], 
            resultado["cliente"], 
            resultado["itens"], 
            resultado["total"], 
            resultado["taxa_entrega"]
        )
        
        return jsonify({
            "sucesso": True,
            "pedido_id": resultado["pedido_id"],
            "resumo": resumo
        })
    except Exception as e:
        app.logger.error(f"Erro no criar_pedido: {e}")
        return jsonify({"sucesso": False, "erro": "Erro ao criar pedido"}), 500

def gerar_resumo_pedido(pedido_id, cliente, itens, total, taxa_entrega=0):
    """Gera o resumo formatado do pedido"""
    resumo = f"""
🍔 PEDIDO #{pedido_id}
👤 Cliente: {cliente}

📋 ITENS:
"""
    for item in itens:
        nome = item.get("nome", "Item")
        qtd = item.get("quantidade", 1)
        preco = item.get("preco", 0)
        resumo += f"  • {qtd}x {nome} - R$ {preco:.2f}\n"
    
    resumo += f"""
🛵 Taxa de entrega: R$ {taxa_entrega:.2f}
💰 TOTAL: R$ {total:.2f}

⏱️ Tempo estimado: 40 a 50 minutos

Obrigado pela preferência! 🎉
"""
    return resumo.strip()

@app.route("/api/pedido/whatsapp")
@login_required
def whatsapp_pedido():
    """Gera link otimizado para WhatsApp usando o serviço"""
    pedido_id = request.args.get("pedido_id")
    
    db = get_connection()
    db.row_factory = sqlite3.Row
    cursor = db.cursor()
    
    cursor.execute("SELECT * FROM pedidos_delivery WHERE id = ? AND restaurante_id = ?", (pedido_id, session.get('restaurante_id', 1)))
    pedido = dict(cursor.fetchone())
    db.close()
    
    if not pedido:
        return jsonify({"sucesso": False, "erro": "Pedido não encontrado!"})
    
    # Parse dos itens
    itens = json.loads(pedido["itens"])
    
    # Usa o serviço para formatar e gerar link
    mensagem = WhatsAppService.formatar_mensagem_pedido(pedido, itens)
    restaurante_id = pedido.get("restaurante_id") or session.get('restaurante_id', 1)
    numero = get_config("whatsapp_restaurante", Config.WHATSAPP_RESTAURANTE, restaurante_id=restaurante_id)
    link = WhatsAppService.gerar_link_whatsapp(mensagem, numero_destino=numero)
    
    return jsonify({
        "sucesso": True, 
        "link": link,
        "resumo": mensagem
    })

# ========================
# NOVO — PIN DO SUPERADMIN
# ========================

@app.route('/superadmin/pin', methods=['GET'])
def superadmin_pin():
    if session.get('role') not in ('superadmin', 'super_admin'):
        return redirect(url_for('login_web'))
    if session.get('superadmin_pin_ok'):
        return redirect('/superadmin')
    return render_template('superadmin_pin.html', erro=None)


@app.route('/superadmin/pin', methods=['POST'])
@csrf.exempt
def superadmin_pin_post():
    if session.get('role') not in ('superadmin', 'super_admin'):
        return redirect(url_for('login_web'))
    pin = request.form.get('pin', '').strip()
    if pin == SUPERADMIN_PIN:
        session['superadmin_pin_ok'] = True
        return redirect('/superadmin')
    return render_template('superadmin_pin.html', erro='PIN incorreto!')


# ========================
# NOVO — PAINEL SUPERADMIN (LICENÇAS)
# ========================

@app.route("/superadmin")
@superadmin_required
def painel_superadmin():
    from datetime import date
    db = get_connection()
    cursor = db.cursor()
    # Garantir coluna restaurante_id em users
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

    # Gerar slug a partir do nome
    slug = unicodedata.normalize('NFD', nome)
    slug = ''.join(c for c in slug if unicodedata.category(c) != 'Mn')
    slug = slug.lower()
    slug = re.sub(r'[^a-z0-9\s-]', '', slug)
    slug = re.sub(r'\s+', '-', slug.strip())
    slug = re.sub(r'-+', '-', slug)

    db = get_connection()
    cursor = db.cursor()

    # Garantir coluna restaurante_id em users
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN restaurante_id INT DEFAULT NULL")
        db.commit()
    except Exception:
        pass

    # Verificar se slug já existe
    cursor.execute("SELECT id FROM restaurantes WHERE slug = %s", (slug,))
    if cursor.fetchone():
        db.close()
        return jsonify({"sucesso": False, "erro": f"Slug '{slug}' já está em uso."}), 409

    # Verificar se username já existe
    cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
    if cursor.fetchone():
        db.close()
        return jsonify({"sucesso": False, "erro": f"Usuário '{username}' já existe."}), 409

    # Inserir restaurante
    cursor.execute(
        "INSERT INTO restaurantes (slug, nome, ativo) VALUES (%s, %s, 1)",
        (slug, nome)
    )
    db.commit()
    restaurante_id = cursor.lastrowid

    # Criar usuário admin vinculado ao restaurante
    password_hash = SecurityService.hash_password(senha)
    cursor.execute(
        "INSERT INTO users (username, password_hash, role, restaurante_id) VALUES (%s, %s, 'admin', %s)",
        (username, password_hash, restaurante_id)
    )
    db.commit()
    db.close()

    return jsonify({"sucesso": True, "slug": slug, "url": f"/cardapio/{slug}"})


# ========================
# NOVO — CONFIGURAÇÕES DO ESTABELECIMENTO
# ========================

@app.route("/api/configuracoes")
def api_configuracoes():
    """Retorna configs públicas para o frontend do cliente."""
    rid = request.args.get('restaurante_id', default=1, type=int)
    return jsonify({
        "sucesso": True,
        "nome_restaurante": get_config("nome_restaurante", "", restaurante_id=rid),
        "taxa_entrega": float(get_config("taxa_entrega", Config.TAXA_ENTREGA, restaurante_id=rid)),
        "frete_por_km": float(get_config("frete_por_km", Config.FRETE_POR_KM, restaurante_id=rid)),
        "restaurante_lat": float(get_config("restaurante_lat", Config.RESTAURANTE_LAT, restaurante_id=rid)),
        "restaurante_lng": float(get_config("restaurante_lng", Config.RESTAURANTE_LNG, restaurante_id=rid)),
        "restaurante_ativo": get_config("restaurante_ativo", "1", restaurante_id=rid),
        "google_maps_key": Config.GOOGLE_MAPS_KEY,
        "whatsapp_restaurante": get_config("whatsapp_restaurante", Config.WHATSAPP_RESTAURANTE, restaurante_id=rid),
    })


@app.route("/admin/toggle-status", methods=["POST"])
@admin_required
def admin_toggle_status():
    """Toggle rápido para abrir/fechar o estabelecimento."""
    atual = get_config("restaurante_ativo", "1", restaurante_id=session['restaurante_id'])
    novo = "0" if atual == "1" else "1"
    set_config("restaurante_ativo", novo, restaurante_id=session['restaurante_id'])
    return jsonify({"restaurante_ativo": novo})


@app.route("/admin/configuracoes", methods=["GET", "POST"])
@admin_required
def admin_configuracoes():
    sucesso = None
    erro = None
    if request.method == "POST":
        campos = [
            "nome_restaurante", "whatsapp_restaurante",
            "frete_por_km", "endereco_restaurante",
            "horario_abertura", "horario_fechamento",
            "restaurante_ativo", "cor_primaria"
        ]
        for campo in campos:
            valor = request.form.get(campo, "").strip()
            if valor != "":
                set_config(campo, valor, restaurante_id=session['restaurante_id'])

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
                              restaurante_id=session['restaurante_id'])
                    set_config("restaurante_lng", str(lng),
                              restaurante_id=session['restaurante_id'])
                else:
                    print("DEBUG geocodificacao ERRO status:", geo_data.get("status"), geo_data)
            except Exception as e:
                print("DEBUG geocodificacao EXCEPTION:", e)
                import traceback
                traceback.print_exc()

        dias = request.form.getlist('dias_funcionamento')
        dias_str = formatar_dias(dias)
        set_config("dias_funcionamento", dias_str, restaurante_id=session['restaurante_id'])

        sucesso = "Configurações salvas com sucesso!"

    configs = {
        "nome_restaurante": get_config("nome_restaurante", "", restaurante_id=session['restaurante_id']),
        "whatsapp_restaurante": get_config("whatsapp_restaurante", Config.WHATSAPP_RESTAURANTE, restaurante_id=session['restaurante_id']),
        "frete_por_km": get_config("frete_por_km", str(Config.FRETE_POR_KM), restaurante_id=session['restaurante_id']),
        "restaurante_lat": get_config("restaurante_lat", str(Config.RESTAURANTE_LAT), restaurante_id=session['restaurante_id']),
        "restaurante_lng": get_config("restaurante_lng", str(Config.RESTAURANTE_LNG), restaurante_id=session['restaurante_id']),
        "horario_abertura": get_config("horario_abertura", "18:00", restaurante_id=session['restaurante_id']),
        "horario_fechamento": get_config("horario_fechamento", "23:00", restaurante_id=session['restaurante_id']),
        "google_maps_key": Config.GOOGLE_MAPS_KEY,
        "restaurante_ativo": get_config("restaurante_ativo", "1", restaurante_id=session['restaurante_id']),
        "endereco_restaurante": get_config("endereco_restaurante", "", restaurante_id=session['restaurante_id']),
        "dias_funcionamento": get_config("dias_funcionamento", "", restaurante_id=session['restaurante_id']),
        "dias_selecionados": parsear_dias(get_config("dias_funcionamento", "", restaurante_id=session['restaurante_id'])),
    }
    return render_template("admin_configuracoes.html", configs=configs, sucesso=sucesso, erro=erro)


# ========================
# ROTAS DO PAINEL DELIVERY
# ========================

@app.route("/delivery")
@login_required
def painel_delivery():
    """Página do painel de pedidos delivery"""
    return render_template("painel_delivery.html")

@app.route("/api/pedidos/delivery")
@login_required
def listar_pedidos_delivery():
    """Retorna todos os pedidos delivery"""
    db = get_connection()
    db.row_factory = sqlite3.Row
    cursor = db.cursor()
    rid = session.get('restaurante_id', 1)

    cursor.execute("""
        SELECT id, cliente_nome, cliente_telefone, cliente_endereco,
               itens, total, status, criado_em
        FROM pedidos_delivery
        WHERE status != 'cancelado'
        AND restaurante_id = ?
        ORDER BY criado_em DESC
    """, (rid,))

    pedidos = []
    for row in cursor.fetchall():
        p = dict(row)
        p["itens"] = json.loads(p["itens"]) if p.get("itens") else []
        pedidos.append(p)

    db.close()
    return jsonify({"sucesso": True, "pedidos": pedidos})

@app.route("/api/pedido/status", methods=["POST"])
@csrf.exempt
@login_required
def atualizar_status_pedido():
    """Atualiza o status de um pedido"""
    dados = request.get_json()
    pedido_id = dados.get("pedido_id")
    novo_status = dados.get("status")

    status_validos = ["novo", "em_preparo", "saiu_entrega", "entregue", "rejeitado"]
    if novo_status not in status_validos:
        return jsonify({"sucesso": False, "erro": "Status inválido!"})

    db = get_connection()
    cursor = db.cursor()
    cursor.execute(
        "UPDATE pedidos_delivery SET status = ? WHERE id = ? AND restaurante_id = ?",
        (novo_status, pedido_id, session.get('restaurante_id', 1))
    )
    db.commit()
    db.close()

    return jsonify({"sucesso": True})

@app.route("/pedido/<int:id>/cancelar", methods=["POST"])
@csrf.exempt
@login_required
def cancelar_pedido(id):
    """Cancela um pedido delivery (muda status para 'cancelado')"""
    db = get_connection()
    cursor = db.cursor()
    cursor.execute(
        "UPDATE pedidos_delivery SET status = 'cancelado' WHERE id = ? AND status = 'novo' AND restaurante_id = ?",
        (id, session.get('restaurante_id', 1))
    )
    alterado = cursor.rowcount
    db.commit()
    db.close()

    if alterado == 0:
        return jsonify({"sucesso": False, "erro": "Pedido não encontrado ou não está como 'novo'."})
    return jsonify({"sucesso": True})

# ========== IMPRESSÃO DE COMANDA ==========

@app.route('/pedido/<int:id>/imprimir')
@login_required
def imprimir_pedido(id):
    db = get_connection()
    cursor = db.cursor()
    cursor.execute(
        "SELECT id, cliente_nome, cliente_telefone, cliente_endereco, itens, taxa_entrega, total, forma_pagamento, troco, status, criado_em FROM pedidos_delivery WHERE id = ? AND restaurante_id = ?",
        (id, session.get('restaurante_id', 1))
    )
    pedido = cursor.fetchone()
    db.close()

    if not pedido:
        return "Pedido não encontrado", 404

    itens = json.loads(pedido[4]) if pedido[4] else []

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
        nome_restaurante=get_config("nome_restaurante", "Comanda Digital")
    )


@app.route('/delivery/imprimir/<int:id>')
@login_required
def delivery_imprimir(id):
    db = get_connection()
    cursor = db.cursor()
    cursor.execute(
        "SELECT id, cliente_nome, cliente_telefone, cliente_endereco, itens, taxa_entrega, total, forma_pagamento, troco, status, criado_em FROM pedidos_delivery WHERE id = ? AND restaurante_id = ?",
        (id, session.get('restaurante_id', 1))
    )
    pedido = cursor.fetchone()
    db.close()

    if not pedido:
        return "Pedido não encontrado", 404

    itens = json.loads(pedido[4]) if pedido[4] else []

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
        nome_restaurante=get_config("nome_restaurante", "Comanda Digital")
    )


@app.route('/mesa/comanda/<numero>')
@login_required
def mesa_comanda(numero):
    from datetime import datetime
    db = get_connection()
    cursor = db.cursor()
    ph = "%s" if is_mysql() else "?"
    cursor.execute(f"SELECT id, numero, total, status FROM mesas WHERE numero = {ph} AND restaurante_id = {ph}", (numero, session.get('restaurante_id', 1)))
    mesa = cursor.fetchone()
    if not mesa:
        return "Mesa não encontrada", 404
    cursor.execute(f"SELECT id, nome, preco, quantidade, observacao FROM itens WHERE mesa_id = {ph} AND restaurante_id = {ph}", (mesa[0], session.get('restaurante_id', 1)))
    itens_raw = cursor.fetchall()
    db.close()
    itens = []
    for i in itens_raw:
        itens.append({
            "id": i[0], "nome": i[1], "preco": float(i[2]),
            "quantidade": i[3], "observacao": i[4] or "",
            "adicionais": []
        })
    return render_template('imprimir_pedido.html',
        pedido_id="MESA-" + str(numero),
        cliente_nome="Mesa " + str(numero),
        cliente_telefone="",
        cliente_endereco="Salão",
        itens=itens,
        taxa_entrega=0,
        total=float(mesa[2]),
        forma_pagamento="",
        troco=0,
        status=mesa[3] if mesa[3] else "aberta",
        criado_em=datetime.now().strftime("%d/%m/%Y %H:%M"),
        nome_restaurante=get_config("nome_restaurante", "Restaurante")
    )


# ========== IMPRESSÃO ESC/POS ==========

@app.route('/api/imprimir/<int:pedido_id>', methods=["POST"])
@csrf.exempt
@login_required
def api_imprimir_escpos(pedido_id):
    """Imprime comanda em impressora térmica via ESC/POS"""
    restaurante_id = session.get('restaurante_id', 1)

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
        return redirect(url_for('mesas'))
    db = get_connection()
    cursor = db.cursor()
    resultados = []

    migracoes = [
        ("pedidos_delivery", "forma_pagamento", "VARCHAR(50) DEFAULT NULL"),
        ("pedidos_delivery", "troco",           "DOUBLE DEFAULT 0"),
    ]

    for tabela, coluna, definicao in migracoes:
        try:
            # Verifica se a coluna já existe
            cursor.execute(f"SHOW COLUMNS FROM {tabela} LIKE '{coluna}'")
            existe = cursor.fetchone()
            if existe:
                # Coluna existe — corrige o tipo com MODIFY
                cursor.execute(f"ALTER TABLE {tabela} MODIFY {coluna} {definicao}")
                db.commit()
                resultados.append(f"CORRIGIDO: '{coluna}' em '{tabela}' → {definicao}")
            else:
                # Coluna não existe — cria
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
    produtos = listar_produtos(session['restaurante_id'])
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
    adicionar_produto(nome, preco, categoria, emoji, session['restaurante_id'], foto, descricao)
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

    editar_produto(id, nome, preco, categoria, emoji, session['restaurante_id'], foto)
    return redirect('/admin/produtos')

@app.route('/admin/produtos/desativar/<int:id>')
@admin_required
def desativar_produto_route(id):
    desativar_produto(id, session['restaurante_id'])
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
        elif not repo.create_custom_admin(username, password, session['restaurante_id'], role):
            erro = f'O usuário "{username}" já existe.'
        else:
            sucesso = f'Usuário "{username}" criado com sucesso!'

    usuarios = repo.list_users(session['restaurante_id'])
    return render_template('admin_usuarios.html', usuarios=usuarios, erro=erro, sucesso=sucesso)

@app.route('/admin/usuarios/remover/<int:user_id>', methods=['POST'])   
@admin_required
def remover_usuario(user_id):
    repo = UserRepository()
    repo.delete_user(user_id, session['user_id'], session['restaurante_id'])
    return redirect('/admin/usuarios')


# ========== MÓDULO DE CAIXA ==========

@app.route("/caixa")
@caixa_or_admin_required
def caixa():
    """Página do módulo de caixa"""
    return render_template("caixa.html")


@app.route("/api/caixa/resumo")
@caixa_or_admin_required
def caixa_resumo():
    """Retorna resumo financeiro da sessão atual do caixa"""
    try:
        db = get_connection()
        if not is_mysql():
            import sqlite3
            db.row_factory = sqlite3.Row
        else:
            db.row_factory = True
        cursor = db.cursor()
        rid = session.get('restaurante_id', 1)

        # Verificar se caixa já foi fechado hoje
        cursor.execute("""
            SELECT id, fechado_em, fechado_por
            FROM caixa_fechamentos
            WHERE data = DATE('now', 'localtime')
            AND restaurante_id = ?
            ORDER BY fechado_em DESC LIMIT 1
        """, (rid,))
        fechamento = cursor.fetchone()

        if fechamento is not None:
            db.close()
            return jsonify({
                "sucesso": True,
                "total_delivery": 0.0,
                "total_mesas": 0.0,
                "total_geral": 0.0,
                "qtd_delivery": 0,
                "qtd_mesas": 0,
                "taxa_entrega_total": 0.0,
                "qtd_entregas_taxa": 0,
                "caixa_fechado": True,
                "fechamento": {
                    "fechado_em": fechamento["fechado_em"],
                    "fechado_por": fechamento["fechado_por"]
                }
            })

        # Obter início da sessão atual
        sessao_inicio = _get_sessao_inicio(cursor, rid)

        # Faturamento delivery (pedidos entregues nesta sessão)
        cursor.execute("""
            SELECT COUNT(*) as qtd, COALESCE(SUM(total), 0) as total,
                   COALESCE(SUM(taxa_entrega), 0) as taxa_total
            FROM pedidos_delivery
            WHERE criado_em >= ?
            AND status = 'entregue'
            AND restaurante_id = ?
        """, (sessao_inicio, rid))
        delivery = cursor.fetchone()

        # Faturamento mesas (fechadas nesta sessão)
        cursor.execute("""
            SELECT COUNT(*) as qtd, COALESCE(SUM(total), 0) as total
            FROM historico_mesas
            WHERE fechado_em >= ?
            AND restaurante_id = ?
        """, (sessao_inicio, rid))
        mesas = cursor.fetchone()

        db.close()

        total_delivery = float(delivery['total'] if isinstance(delivery, dict) else (delivery[1] if delivery else 0))
        total_mesas = float(mesas['total'] if isinstance(mesas, dict) else (mesas[1] if mesas else 0))
        taxa_entrega = float(delivery['taxa_total'] if isinstance(delivery, dict) else (delivery[2] if delivery else 0))
        
        qtd_delivery = int(delivery['qtd'] if isinstance(delivery, dict) else (delivery[0] if delivery else 0))
        qtd_mesas = int(mesas['qtd'] if isinstance(mesas, dict) else (mesas[0] if mesas else 0))

        return jsonify({
            "sucesso": True,
            "total_delivery": total_delivery,
            "total_mesas": total_mesas,
            "total_geral": total_delivery + total_mesas,
            "qtd_delivery": qtd_delivery,
            "qtd_mesas": qtd_mesas,
            "taxa_entrega_total": taxa_entrega,
            "qtd_entregas_taxa": qtd_delivery,
            "caixa_fechado": False
        })
    except Exception as e:
        import traceback
        error_msg = traceback.format_exc()
        with open("caixa_error.log", "a", encoding="utf-8") as f:
            f.write(f"\n--- {datetime.now()} ---\n{error_msg}\n")
        print(f"Erro em /api/caixa/resumo:\n{error_msg}")
        return jsonify({"sucesso": False, "erro": str(e)}), 200


@app.route("/api/caixa/movimentacoes")
@caixa_or_admin_required
def caixa_movimentacoes():
    """Retorna lista de movimentações da sessão atual (delivery + mesas)"""
    try:
        db = get_connection()
        if not is_mysql():
            import sqlite3
            db.row_factory = sqlite3.Row
        else:
            db.row_factory = True
        cursor = db.cursor()
        rid = session.get('restaurante_id', 1)

        sessao_inicio = _get_sessao_inicio(cursor, rid)
        movimentacoes = []

        def get_val(row, key, idx):
            if isinstance(row, dict): return row.get(key)
            return row[idx] if row and len(row) > idx else None

        # Pedidos delivery entregues nesta sessão
        cursor.execute("""
            SELECT id, cliente_nome, total, criado_em
            FROM pedidos_delivery
            WHERE criado_em >= ?
            AND status = 'entregue'
            AND restaurante_id = ?
            ORDER BY criado_em DESC
        """, (sessao_inicio, rid))
        for row in cursor.fetchall():
            movimentacoes.append({
                "tipo": "delivery",
                "descricao": f"Pedido #{get_val(row, 'id', 0)} — {get_val(row, 'cliente_nome', 1)}",
                "valor": float(get_val(row, 'total', 2) or 0),
                "hora": get_val(row, 'criado_em', 3)
            })

        # Mesas fechadas nesta sessão
        cursor.execute("""
            SELECT id, mesa_numero, total, fechado_em
            FROM historico_mesas
            WHERE fechado_em >= ?
            AND restaurante_id = ?
            ORDER BY fechado_em DESC
        """, (sessao_inicio, rid))
        for row in cursor.fetchall():
            movimentacoes.append({
                "tipo": "mesa",
                "descricao": f"Mesa {get_val(row, 'mesa_numero', 1)}",
                "valor": float(get_val(row, 'total', 2) or 0),
                "hora": get_val(row, 'fechado_em', 3)
            })

        # Ordenar por hora (mais recente primeiro)
        movimentacoes.sort(key=lambda x: x["hora"] or "", reverse=True)

        return jsonify({"sucesso": True, "movimentacoes": movimentacoes})
    except Exception as e:
        import traceback
        error_msg = traceback.format_exc()
        with open("caixa_error.log", "a", encoding="utf-8") as f:
            f.write(f"\n--- [MOVIMENTACOES] {datetime.now()} ---\n{error_msg}\n")
        print(f"Erro em /api/caixa/movimentacoes:\n{error_msg}")
        return jsonify({"sucesso": False, "erro": str(e)}), 200


@app.route("/api/caixa/fechar", methods=["POST"])
@caixa_or_admin_required
def fechar_caixa():
    """Fecha o caixa do dia e salva resumo"""
    try:
        db = get_connection()
        if not is_mysql():
            import sqlite3
            db.row_factory = sqlite3.Row
        else:
            db.row_factory = True
        cursor = db.cursor()
        rid = session.get('restaurante_id', 1)

        # 1. Verificar se já foi fechado hoje
        cursor.execute("""
            SELECT id FROM caixa_fechamentos
            WHERE data = DATE('now', 'localtime')
            AND restaurante_id = ?
        """, (rid,))
        if cursor.fetchone():
            db.close()
            return jsonify({"sucesso": False, "erro": "Caixa já foi fechado hoje!"})

        # 2. Buscar totais da sessão atual
        sessao_inicio = _get_sessao_inicio(cursor, rid)

        cursor.execute("""
            SELECT COUNT(*) as qtd, COALESCE(SUM(total), 0) as total
            FROM pedidos_delivery
            WHERE criado_em >= ?
            AND status = 'entregue'
            AND restaurante_id = ?
        """, (sessao_inicio, rid))
        delivery = cursor.fetchone()

        cursor.execute("""
            SELECT COUNT(*) as qtd, COALESCE(SUM(total), 0) as total
            FROM historico_mesas
            WHERE fechado_em >= ?
            AND restaurante_id = ?
        """, (sessao_inicio, rid))
        mesas = cursor.fetchone()

        def get_val(row, key, idx):
            if isinstance(row, dict): return row[key]
            return row[idx] if row else 0

        d_total = float(get_val(delivery, 'total', 1))
        d_qtd = int(get_val(delivery, 'qtd', 0))
        m_total = float(get_val(mesas, 'total', 1))
        m_qtd = int(get_val(mesas, 'qtd', 0))
        total_geral = d_total + m_total
        usuario = session.get("username", "admin")

        # 3. Salvar fechamento em ambas as tabelas (redundância histórica)
        cursor.execute("""
            INSERT INTO caixa_fechamentos
            (data, total_delivery, total_mesas, total_geral, qtd_pedidos_delivery, qtd_mesas, fechado_por, restaurante_id)
            VALUES (DATE('now', 'localtime'), ?, ?, ?, ?, ?, ?, ?)
        """, (d_total, m_total, total_geral, d_qtd, m_qtd, usuario, rid))

        cursor.execute("""
            INSERT INTO fechamentos_caixa
            (data, total_faturado, total_pedidos, total_entregas, valor_entregas, restaurante_id)
            VALUES (DATE('now', 'localtime'), ?, ?, ?, ?, ?)
        """, (total_geral, d_qtd + m_qtd, d_qtd, d_total, rid))

        # 4. Marcar pedidos como fechados
        cursor.execute("""
            UPDATE pedidos_delivery
            SET status = 'fechado'
            WHERE criado_em >= ?
            AND status = 'entregue'
            AND restaurante_id = ?
        """, (sessao_inicio, rid))

        db.commit()
        db.close()

        return jsonify({
            "sucesso": True,
            "total_delivery": d_total,
            "total_mesas": m_total,
            "total_geral": total_geral
        })
    except Exception as e:
        print(f"Erro em fechar_caixa: {e}")
        return jsonify({"sucesso": False, "erro": str(e)}), 500


@app.route("/api/caixa/historico")
@caixa_or_admin_required
def caixa_historico():
    """Retorna fechamentos da tabela fechamentos_caixa filtrados por mês/ano"""
    try:
        mes = request.args.get("mes", "01").zfill(2)
        ano = request.args.get("ano", "2026")
        rid = session.get('restaurante_id', 1)

        db = get_connection()
        if not is_mysql():
            import sqlite3
            db.row_factory = sqlite3.Row
        else:
            db.row_factory = True
        cursor = db.cursor()

        # Busca os fechamentos do mês
        ph = "%s" if is_mysql() else "?"
        
        # SQL compatível com ambos
        if is_mysql():
            cursor.execute("""
                SELECT data, total_faturado, total_pedidos, total_entregas, valor_entregas
                FROM fechamentos_caixa
                WHERE MONTH(data) = %s AND YEAR(data) = %s
                AND restaurante_id = %s
                ORDER BY data ASC
            """, (mes, ano, rid))
        else:
            cursor.execute("""
                SELECT data, total_faturado, total_pedidos, total_entregas, valor_entregas
                FROM fechamentos_caixa
                WHERE strftime('%m', data) = ? AND strftime('%Y', data) = ?
                AND restaurante_id = ?
                ORDER BY data ASC
            """, (mes, ano, rid))

        fechamentos = [dict(row) for row in cursor.fetchall()]
        db.close()

        total_faturado = sum(float(f["total_faturado"]) for f in fechamentos)
        total_pedidos = sum(int(f["total_pedidos"]) for f in fechamentos)
        total_entregas = sum(int(f["total_entregas"]) for f in fechamentos)
        valor_entregas = sum(float(f["valor_entregas"]) for f in fechamentos)

        return jsonify({
            "sucesso": True,
            "fechamentos": fechamentos,
            "totais": {
                "total_faturado": total_faturado,
                "total_pedidos": total_pedidos,
                "total_entregas": total_entregas,
                "valor_entregas": valor_entregas
            }
        })
    except Exception as e:
        print(f"Erro em /api/caixa/historico: {e}")
        return jsonify({"sucesso": False, "erro": str(e)}), 500


@app.route("/api/caixa/abrir", methods=["POST"])
@caixa_or_admin_required
def abrir_caixa():
    """Reabre o caixa removendo o registro de fechamento e inicia nova sessão"""
    try:
        rid = session.get('restaurante_id', 1)
        db = get_connection()
        cursor = db.cursor()
        
        # SQL compatível
        if is_mysql():
            cursor.execute("""
                DELETE FROM caixa_fechamentos
                WHERE DATE(fechado_em) = CURDATE()
                AND restaurante_id = %s
            """, (rid,))
            # Registrar início da nova sessão
            cursor.execute("INSERT INTO caixa_sessoes (aberto_em, restaurante_id) VALUES (NOW(), %s)", (rid,))
        else:
            cursor.execute("""
                DELETE FROM caixa_fechamentos
                WHERE DATE(fechado_em, 'localtime') = DATE('now', 'localtime')
                AND restaurante_id = ?
            """, (rid,))
            # Registrar início da nova sessão
            cursor.execute("INSERT INTO caixa_sessoes (aberto_em, restaurante_id) VALUES (CURRENT_TIMESTAMP, ?)", (rid,))
            
        db.commit()
        db.close()
        return jsonify({"sucesso": True})
    except Exception as e:
        print(f"Erro em abrir_caixa: {e}")
        return jsonify({"sucesso": False, "erro": str(e)}), 500


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
        rid = session.get('restaurante_id', 1)

        sessao_inicio = _get_sessao_inicio(cursor, rid)
        horas = {h: 0.0 for h in range(24)}

        def get_val(row, key, idx):
            if isinstance(row, dict): return row.get(key)
            return row[idx] if row and len(row) > idx else None

        # Delivery por hora
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
            h = get_val(row, 'hora', 0)
            if h is not None:
                horas[int(h)] += float(get_val(row, 'total', 1))

        # Mesas por hora
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
        error_msg = traceback.format_exc()
        with open("caixa_error.log", "a", encoding="utf-8") as f:
            f.write(f"\n--- [GRAFICO] {datetime.now()} ---\n{error_msg}\n")
        print(f"Erro em /api/caixa/grafico:\n{error_msg}")
        return jsonify({"sucesso": False, "erro": str(e)}), 200

@app.route("/api/caixa/balanco")
@caixa_or_admin_required
def caixa_balanco():
    """Retorna balanço mensal agrupado por dia"""
    try:
        mes = request.args.get("mes", "01").zfill(2)
        ano = request.args.get("ano", "2026")
        rid = session.get('restaurante_id', 1)

        db = get_connection()
        if not is_mysql():
            import sqlite3
            db.row_factory = sqlite3.Row
        else:
            db.row_factory = True
        cursor = db.cursor()

        # Busca todos os fechamentos do mês
        ph = "%s" if is_mysql() else "?"
        cursor.execute(f"""
            SELECT DATE(criado_em) as data, total_delivery, total_mesas, total_geral,
                   qtd_pedidos_delivery, qtd_mesas, fechado_por
            FROM caixa_fechamentos
            WHERE {"MONTH(criado_em)" if is_mysql() else "strftime('%m', criado_em)"} = {ph} 
            AND {"YEAR(criado_em)" if is_mysql() else "strftime('%Y', criado_em)"} = {ph}
            AND restaurante_id = {ph}
            ORDER BY criado_em ASC
        """, (mes, ano, rid))

        dias = [dict(row) for row in cursor.fetchall()]

        # Totais do mês
        total_mes_delivery = sum(float(d.get("total_delivery", 0)) for d in dias)
        total_mes_mesas = sum(float(d.get("total_mesas", 0)) for d in dias)
        total_mes_geral = sum(float(d.get("total_geral", 0)) for d in dias)
        qtd_mes_delivery = sum(int(d.get("qtd_pedidos_delivery", 0)) for d in dias)
        qtd_mes_mesas = sum(int(d.get("qtd_mesas", 0)) for d in dias)

        db.close()

        return jsonify({
            "sucesso": True,
            "mes": mes,
            "ano": ano,
            "dias": dias,
            "totais": {
                "total_delivery": total_mes_delivery,
                "total_mesas": total_mes_mesas,
                "total_geral": total_mes_geral,
                "qtd_delivery": qtd_mes_delivery,
                "qtd_mesas": qtd_mes_mesas,
                "dias_trabalhados": len(dias)
            }
        })
    except Exception as e:
        print(f"Erro em /api/caixa/balanco: {e}")
        return jsonify({"sucesso": False, "erro": str(e)}), 500


# ========== GOOGLE MAPS / FRETE ==========

@app.route("/api/maps/config")
@csrf.exempt
def maps_config():
    """Retorna configuração do Google Maps para o frontend"""
    return jsonify({
        "sucesso": True,
        "api_key": Config.GOOGLE_MAPS_KEY,
        "restaurante_lat": Config.RESTAURANTE_LAT,
        "restaurante_lng": Config.RESTAURANTE_LNG,
        "frete_por_km": Config.FRETE_POR_KM
    })


@app.route("/api/maps/calcular-frete", methods=["POST"])
@csrf.exempt
def calcular_frete():
    """Calcula frete via Distance Matrix API com fallback Haversine"""
    import math
    import requests as http_requests

    dados = request.get_json()
    cliente_lat = dados.get("lat")
    cliente_lng = dados.get("lng")
    endereco_destino = dados.get("endereco_destino")
    rid = dados.get("restaurante_id", 1)

    if endereco_destino is None and (cliente_lat is None or cliente_lng is None):
        return jsonify({"sucesso": False, "erro": "Coordenadas não informadas!"})

    frete_por_km = float(get_config("frete_por_km", Config.FRETE_POR_KM, restaurante_id=rid))
    google_maps_key = Config.GOOGLE_MAPS_KEY
    rest_lat = float(get_config("restaurante_lat", Config.RESTAURANTE_LAT, restaurante_id=rid))
    rest_lng = float(get_config("restaurante_lng", Config.RESTAURANTE_LNG, restaurante_id=rid))

    destinations = endereco_destino if endereco_destino else f"{cliente_lat},{cliente_lng}"

    distancia_km = None

    # Tenta Distance Matrix API
    try:
        resp = http_requests.get(
            "https://maps.googleapis.com/maps/api/distancematrix/json",
            params={
                "origins": f"{rest_lat},{rest_lng}",
                "destinations": destinations,
                "key": google_maps_key
            },
            timeout=5
        )
        resultado = resp.json()
        if resultado.get("status") == "OK":
            distancia_km = resultado["rows"][0]["elements"][0]["distance"]["value"] / 1000
    except Exception:
        pass

    # Fallback Haversine (apenas quando lat/lng disponíveis)
    if distancia_km is None and cliente_lat is not None and cliente_lng is not None:
        R = 6371
        dlat = math.radians(cliente_lat - rest_lat)
        dlng = math.radians(cliente_lng - rest_lng)
        a = (math.sin(dlat / 2) ** 2 +
             math.cos(math.radians(rest_lat)) * math.cos(math.radians(cliente_lat)) *
             math.sin(dlng / 2) ** 2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        distancia_km = R * c

    if distancia_km is None:
        return jsonify({"sucesso": False, "erro": "Não foi possível calcular a distância!"})

    frete = round(distancia_km * frete_por_km, 2)

    return jsonify({"sucesso": True, "frete": frete, "distancia_km": round(distancia_km, 2)})


@app.route("/carrinho")
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
# ROTAS MULTI-TENANT
# ========================

@app.route("/cardapio/<slug>")
def cardapio_por_slug(slug):
    from data.db import get_connection
    db = get_connection()
    cursor = db.cursor()
    cursor.execute("SELECT id, nome, ativo FROM restaurantes WHERE slug = %s", (slug,))
    row = cursor.fetchone()
    db.close()
    if not row:
        abort(404)
    restaurante_id, nome, ativo = row[0], row[1], row[2]
    if not ativo:
        return render_template("restaurante_inativo.html")
    verificar_horario_funcionamento(restaurante_id)
    return render_template("cardapio_cliente.html", slug=slug, restaurante_nome=nome,
        restaurante_id=restaurante_id,
        whatsapp_restaurante=get_config('whatsapp_restaurante', Config.WHATSAPP_RESTAURANTE, restaurante_id),
        google_maps_key=Config.GOOGLE_MAPS_KEY)

@app.route("/cardapio/<slug>/api/cardapio")
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
def api_restaurante_por_slug(slug):
    from data.db import get_connection
    from datetime import datetime

    db = get_connection()
    cursor = db.cursor()
    cursor.execute("SELECT id, nome, ativo FROM restaurantes WHERE slug = %s", (slug,))
    row = cursor.fetchone()
    db.close()

    if not row:
        return jsonify({"sucesso": False, "erro": "Restaurante não encontrado"}), 404

    restaurante_id, nome, ativo_db = row[0], row[1], row[2]

    horario_abertura = get_config("horario_abertura", "18:00", restaurante_id)
    horario_fechamento = get_config("horario_fechamento", "23:00", restaurante_id)
    dias_funcionamento = get_config("dias_funcionamento", "", restaurante_id)
    restaurante_ativo = get_config("restaurante_ativo", "1", restaurante_id)

    if restaurante_ativo == "0" or not ativo_db:
        status = "fechado"
    else:
        try:
            agora = datetime.now().time()
            abertura = datetime.strptime(horario_abertura, "%H:%M").time()
            fechamento = datetime.strptime(horario_fechamento, "%H:%M").time()
            status = "aberto" if abertura <= agora <= fechamento else "fechado"
        except Exception:
            status = "fechado"

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


@app.route("/api/check-status/<int:restaurant_id>")
def api_check_status(restaurant_id):
    verificar_horario_funcionamento(restaurant_id)
    db = get_connection()
    cursor = db.cursor()
    if is_mysql():
        cursor.execute("SELECT status FROM restaurantes WHERE id = %s", (restaurant_id,))
    else:
        cursor.execute("SELECT status FROM restaurantes WHERE id = ?", (restaurant_id,))
    row = cursor.fetchone()
    db.close()
    status = row[0] if row else "fechado"
    return jsonify({"status": status})


@app.route('/admin/adicionais')
@admin_required
def admin_adicionais():
    adicionais = listar_adicionais_com_categorias(session['restaurante_id'])
    categorias = listar_categorias_produtos(session['restaurante_id'])
    return render_template('admin_adicionais.html', adicionais=adicionais, categorias=categorias)

@app.route('/admin/adicionais/adicionar', methods=['POST'])
@admin_required
def adicionar_adicional_route():
    nome = request.form['nome'].strip()
    preco = float(request.form['preco'])
    categorias = request.form.getlist('categorias')
    if nome and preco >= 0 and categorias:
        adicionar_adicional(nome, preco, categorias, session['restaurante_id'])
    return redirect('/admin/adicionais')

@app.route('/admin/adicionais/editar/<int:id>', methods=['POST'])
@admin_required
def editar_adicional_route(id):
    nome = request.form['nome'].strip()
    preco = float(request.form['preco'])
    categorias = request.form.getlist('categorias')
    editar_adicional(id, nome, preco, categorias, session['restaurante_id'])
    return redirect('/admin/adicionais')

@app.route('/admin/adicionais/desativar/<int:id>', methods=['POST'])
@admin_required
def desativar_adicional_route(id):
    desativar_adicional(id, session['restaurante_id'])
    return redirect('/admin/adicionais')

@app.route('/admin/adicionais/excluir/<int:id>', methods=['POST'])
@admin_required
def excluir_adicional_route(id):
    excluir_adicional(id, session['restaurante_id'])
    return jsonify({"sucesso": True})

@app.route('/api/categorias')
def api_categorias():
    categorias = listar_categorias_produtos(session['restaurante_id'])
    return jsonify({"sucesso": True, "categorias": categorias})


@app.route("/admin/categorias")
@admin_required
def admin_categorias():
    categorias = listar_categorias_produtos(session['restaurante_id'])
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
def get_cliente(telefone):
    db = get_connection()
    cursor = db.cursor()
    cursor.execute(
        "SELECT nome, endereco FROM clientes_cache WHERE telefone = ?",
        (telefone,)
    )
    row = cursor.fetchone()
    db.close()
    if row:
        return jsonify({"sucesso": True, "nome": row[0], "endereco": row[1]})
    return jsonify({"sucesso": False})


@app.route("/api/cliente", methods=["POST"])
@csrf.exempt
def salvar_cliente():
    dados = request.get_json()
    telefone = dados.get("telefone", "").strip()
    nome = dados.get("nome", "").strip()
    endereco = dados.get("endereco", "").strip()
    if not telefone:
        return jsonify({"sucesso": False})
    db = get_connection()
    cursor = db.cursor()
    if is_mysql():
        cursor.execute("""
            INSERT INTO clientes_cache (telefone, nome, endereco)
            VALUES (%s, %s, %s)
            ON DUPLICATE KEY UPDATE nome=%s, endereco=%s
        """, (telefone, nome, endereco, nome, endereco))
    else:
        cursor.execute("""
            INSERT INTO clientes_cache (telefone, nome, endereco)
            VALUES (?, ?, ?)
            ON CONFLICT(telefone) DO UPDATE SET nome=excluded.nome, endereco=excluded.endereco
        """, (telefone, nome, endereco))
    db.commit()
    db.close()
    return jsonify({"sucesso": True})



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
