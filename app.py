import json
import os
import logging
from repository import listar_adicionais, listar_produtos, adicionar_produto, editar_produto, desativar_produto, adicionar_adicional, desativar_adicional
import urllib.parse
from services.whatsapp_service import WhatsAppService
from repository import UserRepository
from security import SecurityService
from config import Config
from flask import Flask, render_template, jsonify, request, session, redirect, url_for
from data.db import init_db, get_connection
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
        'script-src': "'self' 'unsafe-inline'",
        'style-src': "'self' 'unsafe-inline'",
        'img-src': "'self' data:",
        'font-src': "'self' data:",
    },
    session_cookie_secure=True,
)

# Extensões e tamanho máximo de upload
EXTENSOES_PERMITIDAS = {'.jpg', '.jpeg', '.png', '.webp', '.gif'}
MAX_FILE_SIZE = 16 * 1024 * 1024  # 16MB
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE

def extensao_valida(filename):
    return os.path.splitext(filename)[1].lower() in EXTENSOES_PERMITIDAS

app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    SESSION_COOKIE_SECURE=True,
    PERMANENT_SESSION_LIFETIME=1800
)
# Inicia o banco usando o db.py
#init_db()

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
        if session.get('role') not in ('admin', 'superadmin'):
            return redirect(url_for('mesas'))
        return f(*args, **kwargs)
    return decorated_function

# ========================
# ROTAS DE AUTENTICAÇÃO
# ========================
@app.route("/login", methods=['GET', 'POST'])
@limiter.limit("5 per minute")
def login_web():
    if request.method == 'POST':
        username = request.form.get('username').strip()
        password = request.form.get('password').strip()
        
        repo = UserRepository()
        user = repo.get_user_by_username(username)
        
        if user and SecurityService.verify_password(password, user.password_hash):
            session['user_id'] = user.id
            session['username'] = user.username
            session['role'] = user.role
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
    if role == 'admin':
        return render_template('dashboard.html')
    elif role == 'atendente':
        return render_template('atendente.html')
    elif role == 'caixa':
        return render_template('caixa.html')
    else:
        return redirect(url_for('login_web'))


@app.route("/mesas")
@login_required
def mesas():
    role = session.get('role')
    if role == 'atendente':
        return render_template("atendente.html")
    else:
        return redirect(url_for('index'))

@app.route("/api/dashboard/resumo")
@login_required
def dashboard_resumo():
    """Retorna contadores para o dashboard"""
    db = get_connection()
    db.row_factory = __import__('sqlite3').Row
    cursor = db.cursor()

    # Mesas abertas
    cursor.execute("SELECT COUNT(*) as total FROM mesas")
    mesas_abertas = cursor.fetchone()["total"]

    # Pedidos delivery por status
    cursor.execute("""
        SELECT status, COUNT(*) as total FROM pedidos_delivery
        WHERE status != 'entregue'
        GROUP BY status
    """)
    pedidos_por_status = {row["status"]: row["total"] for row in cursor.fetchall()}

    # Total de pedidos hoje (todos os status)
    cursor.execute("""
        SELECT COUNT(*) as total
        FROM pedidos_delivery
        WHERE DATE(criado_em, 'localtime') = DATE('now', 'localtime')
    """)
    pedidos_hoje = cursor.fetchone()["total"]

    # Faturamento hoje (apenas pedidos entregues)
    cursor.execute("""
        SELECT COALESCE(SUM(total), 0) as faturamento
        FROM pedidos_delivery
        WHERE DATE(criado_em, 'localtime') = DATE('now', 'localtime')
        AND status = 'entregue'
    """)
    faturamento_hoje = cursor.fetchone()["faturamento"]

    db.close()
    return jsonify({
        "sucesso": True,
        "mesas_abertas": mesas_abertas,
        "pedidos_novos": pedidos_por_status.get("novo", 0),
        "pedidos_preparo": pedidos_por_status.get("em_preparo", 0),
        "pedidos_entrega": pedidos_por_status.get("saiu_entrega", 0),
        "pedidos_hoje": pedidos_hoje,
        "faturamento_hoje": faturamento_hoje
    })

@app.route("/api/mesas")
@login_required
def listar_mesas():
    db = get_connection()
    db.row_factory = __import__('sqlite3').Row
    cursor = db.cursor()

    cursor.execute("SELECT id, numero, total FROM mesas")
    mesas_db = cursor.fetchall()

    mesas = []
    for mesa in mesas_db:
        cursor.execute(
            "SELECT id, nome, preco, quantidade, observacao FROM itens WHERE mesa_id = ?",
            (mesa["id"],)
        )
        itens = [dict(i) for i in cursor.fetchall()]

        mesas.append({
            "id": mesa["id"],
            "numero": mesa["numero"],
            "total": mesa["total"],
            "itens": itens
        })

    db.close()
    return jsonify({"sucesso": True, "mesas": mesas})

@app.route("/api/mesa/abrir", methods=["POST"])
@login_required
def abrir_mesa():
    dados = request.get_json()
    num = str(dados.get("numero"))

    db = get_connection()
    cursor = db.cursor()

    cursor.execute("SELECT numero FROM mesas WHERE numero = ?", (num,))
    if cursor.fetchone():
        db.close()
        return jsonify({"sucesso": False, "erro": "Mesa já aberta!"})

    cursor.execute(
        "INSERT INTO mesas (numero, total) VALUES (?, ?)",
        (num, 0.0)
    )
    db.commit()
    db.close()

    return jsonify({"sucesso": True})

@app.route("/api/mesa/item", methods=["POST"])
@login_required
def adicionar_item():
    dados = request.get_json()
    num = str(dados.get("numero"))

    db = get_connection()
    cursor = db.cursor()

    cursor.execute("SELECT id FROM mesas WHERE numero = ?", (num,))
    mesa = cursor.fetchone()
    if not mesa:
        db.close()
        return jsonify({"sucesso": False, "erro": "Mesa não encontrada!"})

    mesa_id = mesa[0]
    nome = dados.get("nome")
    preco = float(dados.get("preco"))
    quantidade = int(dados.get("quantidade", 1))
    observacao = dados.get("observacao", "")

    cursor.execute("""
        INSERT INTO itens (mesa_id, nome, preco, quantidade, observacao)
        VALUES (?, ?, ?, ?, ?)
    """, (mesa_id, nome, preco, quantidade, observacao))

    cursor.execute("""
        SELECT SUM(preco * quantidade) FROM itens WHERE mesa_id = ?
    """, (mesa_id,))
    total = cursor.fetchone()[0] or 0

    cursor.execute(
        "UPDATE mesas SET total = ? WHERE id = ?",
        (total, mesa_id)
    )

    db.commit()
    db.close()
    return jsonify({"sucesso": True})


@app.route("/api/mesa/item/remover", methods=["POST"])
@login_required
def remover_item():
    dados = request.get_json()
    item_id = int(dados.get("id"))

    db = get_connection()
    cursor = db.cursor()

    cursor.execute("SELECT mesa_id FROM itens WHERE id = ?", (item_id,))
    row = cursor.fetchone()
    if not row:
        db.close()
        return jsonify({"sucesso": False, "erro": "Item não encontrado"})

    mesa_id = row[0]

    cursor.execute("DELETE FROM itens WHERE id = ?", (item_id,))

    cursor.execute("""
        SELECT SUM(preco * quantidade) FROM itens WHERE mesa_id = ?
    """, (mesa_id,))
    total = cursor.fetchone()[0] or 0

    cursor.execute(
        "UPDATE mesas SET total = ? WHERE id = ?",
        (total, mesa_id)
    )

    db.commit()
    db.close()
    return jsonify({"sucesso": True})


@app.route("/api/mesa/fechar", methods=["POST"])
@login_required
def fechar_mesa():
    dados = request.get_json()
    num = str(dados.get("numero"))

    db = get_connection()
    cursor = db.cursor()

    cursor.execute("SELECT id FROM mesas WHERE numero = ?", (num,))
    mesa = cursor.fetchone()
    if not mesa:
        db.close()
        return jsonify({"sucesso": False, "erro": "Mesa não encontrada!"})

    mesa_id = mesa[0]

    # Salvar histórico da mesa antes de deletar
    cursor.execute("SELECT numero, total FROM mesas WHERE id = ?", (mesa_id,))
    mesa_info = cursor.fetchone()
    cursor.execute("SELECT nome, preco, quantidade, observacao FROM itens WHERE mesa_id = ?", (mesa_id,))
    itens_mesa = cursor.fetchall()
    itens_json = json.dumps([{"nome": i[0], "preco": i[1], "quantidade": i[2], "observacao": i[3]} for i in itens_mesa], ensure_ascii=False)
    cursor.execute(
        "INSERT INTO historico_mesas (mesa_numero, total, itens) VALUES (?, ?, ?)",
        (mesa_info[0], mesa_info[1], itens_json)
    )

    cursor.execute("DELETE FROM itens WHERE mesa_id = ?", (mesa_id,))
    cursor.execute("DELETE FROM mesas WHERE id = ?", (mesa_id,))

    db.commit()
    db.close()
    return jsonify({"sucesso": True})


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
    return render_template("cardapio_cliente.html")
@app.route("/api/cardapio")
def api_cardapio():
    """Retorna os produtos do cardápio"""
    produtos = listar_produtos()
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

@app.route("/api/adicionais")
def api_adicionais():
    produto_id = request.args.get('produto_id', type=int)
    adicionais = listar_adicionais(produto_id=produto_id)
    resultado = []
    for a in adicionais:
        resultado.append({
            "id": a[0],
            "nome": a[1],
            "preco": a[2]
        })
    return jsonify({"sucesso": True, "adicionais": resultado})

@app.route("/api/pedido", methods=["POST"])
@csrf.exempt
def criar_pedido():
    """Cria um novo pedido delivery"""
    dados = request.get_json()
    
    cliente_nome = dados.get("nome")
    cliente_telefone = dados.get("telefone")
    cliente_endereco = dados.get("endereco")
    itens = dados.get("itens", [])
    taxa_entrega = 5.00
    
    if not itens or not cliente_nome:
        return jsonify({"sucesso": False, "erro": "Dados incompletos!"})
    
    # Calcula total
    total = sum(item.get("preco", 0) * item.get("quantidade", 1) for item in itens)
    total += taxa_entrega
    
    # Salva no banco
    db = get_connection()
    cursor = db.cursor()
    cursor.execute("""
        INSERT INTO pedidos_delivery 
        (cliente_nome, cliente_telefone, cliente_endereco, itens, taxa_entrega, total, status)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        cliente_nome,
        cliente_telefone,
        cliente_endereco,
        json.dumps(itens, ensure_ascii=False),
        taxa_entrega,
        total,
        'novo'
    ))
    
    pedido_id = cursor.lastrowid
    db.commit()
    db.close()
    
    # Gera resumo do pedido
    resumo = gerar_resumo_pedido(pedido_id, cliente_nome, itens, total)
    
    return jsonify({
        "sucesso": True,
        "pedido_id": pedido_id,
        "resumo": resumo
    })

def gerar_resumo_pedido(pedido_id, cliente, itens, total):
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
🛵 Taxa de entrega: R$ 5,00
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
    db.row_factory = __import__('sqlite3').Row
    cursor = db.cursor()
    
    cursor.execute("SELECT * FROM pedidos_delivery WHERE id = ?", (pedido_id,))
    pedido = dict(cursor.fetchone())
    db.close()
    
    if not pedido:
        return jsonify({"sucesso": False, "erro": "Pedido não encontrado!"})
    
    # Parse dos itens
    itens = json.loads(pedido["itens"])
    
    # Usa o serviço para formatar e gerar link
    mensagem = WhatsAppService.formatar_mensagem_pedido(pedido, itens)
    link = WhatsAppService.gerar_link_whatsapp(mensagem)
    
    return jsonify({
        "sucesso": True, 
        "link": link,
        "resumo": mensagem
    })

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
    """Retorna todos os pedidos delivery (exceto entregues)"""
    db = get_connection()
    db.row_factory = __import__('sqlite3').Row
    cursor = db.cursor()

    cursor.execute("""
        SELECT id, cliente_nome, cliente_telefone, cliente_endereco,
               itens, total, status, criado_em
        FROM pedidos_delivery
        WHERE status != 'entregue'
        ORDER BY criado_em DESC
    """)

    pedidos = []
    for row in cursor.fetchall():
        p = dict(row)
        p["itens"] = json.loads(p["itens"])
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

    status_validos = ["novo", "em_preparo", "saiu_entrega", "entregue"]
    if novo_status not in status_validos:
        return jsonify({"sucesso": False, "erro": "Status inválido!"})

    db = get_connection()
    cursor = db.cursor()
    cursor.execute(
        "UPDATE pedidos_delivery SET status = ? WHERE id = ?",
        (novo_status, pedido_id)
    )
    db.commit()
    db.close()

    return jsonify({"sucesso": True})

# ========== IMPRESSÃO DE COMANDA ==========

@app.route('/pedido/<int:id>/imprimir')
@login_required
def imprimir_pedido(id):
    db = get_connection()
    cursor = db.cursor()
    cursor.execute(
        "SELECT id, cliente_nome, cliente_telefone, cliente_endereco, itens, taxa_entrega, total, status, criado_em FROM pedidos_delivery WHERE id = ?",
        (id,)
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
        status=pedido[7],
        criado_em=pedido[8]
    )

# ========== ADMIN PRODUTOS ==========

@app.route('/admin/produtos')
@admin_required
def admin_produtos():
    produtos = listar_produtos()
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
            caminho_salvar = f'static/img/produtos/{nome_seguro}'
 

            img = Image.open(arquivo)
            img.thumbnail((800, 800))  # redimensiona mantendo proporção

        # Converte para RGB se necessário (PNG com transparência, etc)
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")

            img.save(caminho_salvar, optimize=True, quality=75)
            foto = nome_seguro

    descricao = request.form.get('descricao', '').strip() or None
    adicionar_produto(nome, preco, categoria, emoji, foto, descricao)
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
            caminho_salvar = f'static/img/produtos/{nome_seguro}'
            arquivo.save(caminho_salvar)
            foto = nome_seguro

    editar_produto(id, nome, preco, categoria, emoji, foto)
    return redirect('/admin/produtos')

@app.route('/admin/produtos/desativar/<int:id>')
@admin_required
def desativar_produto_route(id):
    desativar_produto(id)
    return redirect('/admin/produtos')

# ========== ADMIN ADICIONAIS ==========

@app.route('/admin/adicionais')
@admin_required
def admin_adicionais():
    adicionais = listar_adicionais()
    produtos = listar_produtos()
    return render_template('admin_adicionais.html', adicionais=adicionais, produtos=produtos)

@app.route('/admin/adicionais/adicionar', methods=['POST'])
@admin_required
def adicionar_adicional_route():
    nome = request.form['nome']
    preco = float(request.form['preco'])
    produto_id = request.form.get('produto_id', '').strip()
    produto_id = int(produto_id) if produto_id else None
    adicionar_adicional(nome, preco, produto_id)
    return redirect('/admin/adicionais')

@app.route('/admin/adicionais/desativar/<int:id>')
@admin_required
def desativar_adicional_route(id):
    desativar_adicional(id)
    return redirect('/admin/adicionais')

# ========== ALTERAR SENHA ==========

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
        if role not in ('admin', 'atendente'):
            role = 'atendente'

        if not username or not password:
            erro = 'Preencha usuário e senha.'
        elif len(password) < 6:
            erro = 'A senha deve ter pelo menos 6 caracteres.'
        elif password != confirmar:
            erro = 'As senhas não coincidem.'
        elif not repo.create_custom_admin(username, password, role):
            erro = f'O usuário "{username}" já existe.'
        else:
            sucesso = f'Usuário "{username}" criado com sucesso!'

    usuarios = repo.list_users()
    return render_template('admin_usuarios.html', usuarios=usuarios, erro=erro, sucesso=sucesso)

@app.route('/admin/usuarios/remover/<int:user_id>', methods=['POST'])   
@admin_required
def remover_usuario(user_id):
    repo = UserRepository()
    repo.delete_user(user_id, session['user_id'])
    return redirect('/admin/usuarios')


# ========== MÓDULO DE CAIXA ==========

@app.route("/caixa")
@admin_required
def caixa():
    """Página do módulo de caixa"""
    return render_template("caixa.html")


@app.route("/api/caixa/resumo")
@admin_required
def caixa_resumo():
    """Retorna resumo financeiro do dia para o caixa"""
    db = get_connection()
    db.row_factory = __import__('sqlite3').Row
    cursor = db.cursor()

    # Faturamento delivery (pedidos entregues hoje)
    cursor.execute("""
        SELECT COUNT(*) as qtd, COALESCE(SUM(total), 0) as total
        FROM pedidos_delivery
        WHERE DATE(criado_em, 'localtime') = DATE('now', 'localtime')
        AND status = 'entregue'
    """)
    delivery = cursor.fetchone()

    # Faturamento mesas (fechadas hoje)
    cursor.execute("""
        SELECT COUNT(*) as qtd, COALESCE(SUM(total), 0) as total
        FROM historico_mesas
        WHERE DATE(fechado_em, 'localtime') = DATE('now', 'localtime')
    """)
    mesas = cursor.fetchone()

    # Verificar se caixa já foi fechado hoje
    cursor.execute("""
        SELECT id, fechado_em, fechado_por
        FROM caixa_fechamentos
        WHERE data = DATE('now', 'localtime')
        ORDER BY fechado_em DESC LIMIT 1
    """)
    fechamento = cursor.fetchone()

    db.close()

    total_delivery = delivery["total"]
    total_mesas = mesas["total"]

    return jsonify({
        "sucesso": True,
        "total_delivery": total_delivery,
        "total_mesas": total_mesas,
        "total_geral": total_delivery + total_mesas,
        "qtd_delivery": delivery["qtd"],
        "qtd_mesas": mesas["qtd"],
        "caixa_fechado": fechamento is not None,
        "fechamento": {
            "fechado_em": fechamento["fechado_em"],
            "fechado_por": fechamento["fechado_por"]
        } if fechamento else None
    })


@app.route("/api/caixa/movimentacoes")
@admin_required
def caixa_movimentacoes():
    """Retorna lista de movimentações do dia (delivery + mesas)"""
    db = get_connection()
    db.row_factory = __import__('sqlite3').Row
    cursor = db.cursor()

    movimentacoes = []

    # Pedidos delivery entregues hoje
    cursor.execute("""
        SELECT id, cliente_nome, total, criado_em
        FROM pedidos_delivery
        WHERE DATE(criado_em, 'localtime') = DATE('now', 'localtime')
        AND status = 'entregue'
        ORDER BY criado_em DESC
    """)
    for row in cursor.fetchall():
        movimentacoes.append({
            "tipo": "delivery",
            "descricao": f"Pedido #{row['id']} — {row['cliente_nome']}",
            "valor": row["total"],
            "hora": row["criado_em"]
        })

    # Mesas fechadas hoje
    cursor.execute("""
        SELECT id, mesa_numero, total, fechado_em
        FROM historico_mesas
        WHERE DATE(fechado_em, 'localtime') = DATE('now', 'localtime')
        ORDER BY fechado_em DESC
    """)
    for row in cursor.fetchall():
        movimentacoes.append({
            "tipo": "mesa",
            "descricao": f"Mesa {row['mesa_numero']}",
            "valor": row["total"],
            "hora": row["fechado_em"]
        })

    # Ordenar por hora (mais recente primeiro)
    movimentacoes.sort(key=lambda x: x["hora"] or "", reverse=True)

    db.close()
    return jsonify({"sucesso": True, "movimentacoes": movimentacoes})


@app.route("/api/caixa/fechar", methods=["POST"])
@admin_required
def fechar_caixa():
    """Registra o fechamento do caixa do dia"""
    db = get_connection()
    db.row_factory = __import__('sqlite3').Row
    cursor = db.cursor()

    # Verificar se já foi fechado hoje
    cursor.execute("""
        SELECT id FROM caixa_fechamentos
        WHERE data = DATE('now', 'localtime')
    """)
    if cursor.fetchone():
        db.close()
        return jsonify({"sucesso": False, "erro": "Caixa já foi fechado hoje!"})

    # Buscar totais do dia
    cursor.execute("""
        SELECT COUNT(*) as qtd, COALESCE(SUM(total), 0) as total
        FROM pedidos_delivery
        WHERE DATE(criado_em, 'localtime') = DATE('now', 'localtime')
        AND status = 'entregue'
    """)
    delivery = cursor.fetchone()

    cursor.execute("""
        SELECT COUNT(*) as qtd, COALESCE(SUM(total), 0) as total
        FROM historico_mesas
        WHERE DATE(fechado_em, 'localtime') = DATE('now', 'localtime')
    """)
    mesas = cursor.fetchone()

    total_delivery = delivery["total"]
    total_mesas = mesas["total"]
    total_geral = total_delivery + total_mesas

    usuario = session.get("username", "admin")

    cursor.execute("""
        INSERT INTO caixa_fechamentos
        (data, total_delivery, total_mesas, total_geral, qtd_pedidos_delivery, qtd_mesas, fechado_por)
        VALUES (DATE('now', 'localtime'), ?, ?, ?, ?, ?, ?)
    """, (total_delivery, total_mesas, total_geral, delivery["qtd"], mesas["qtd"], usuario))

    db.commit()
    db.close()

    return jsonify({
        "sucesso": True,
        "total_delivery": total_delivery,
        "total_mesas": total_mesas,
        "total_geral": total_geral
    })


@app.route("/api/caixa/grafico")
@admin_required
def caixa_grafico():
    """Retorna faturamento agrupado por hora para gráfico"""
    db = get_connection()
    db.row_factory = __import__('sqlite3').Row
    cursor = db.cursor()

    horas = {}
    for h in range(24):
        horas[h] = 0.0

    # Delivery por hora
    cursor.execute("""
        SELECT CAST(strftime('%H', criado_em, 'localtime') AS INTEGER) as hora,
               COALESCE(SUM(total), 0) as total
        FROM pedidos_delivery
        WHERE DATE(criado_em, 'localtime') = DATE('now', 'localtime')
        AND status = 'entregue'
        GROUP BY hora
    """)
    for row in cursor.fetchall():
        horas[row["hora"]] += row["total"]

    # Mesas por hora
    cursor.execute("""
        SELECT CAST(strftime('%H', fechado_em, 'localtime') AS INTEGER) as hora,
               COALESCE(SUM(total), 0) as total
        FROM historico_mesas
        WHERE DATE(fechado_em, 'localtime') = DATE('now', 'localtime')
        GROUP BY hora
    """)
    for row in cursor.fetchall():
        horas[row["hora"]] += row["total"]

    db.close()

    return jsonify({
        "sucesso": True,
        "horas": [{"hora": h, "total": horas[h]} for h in sorted(horas.keys())]
    })


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
    """Calcula frete baseado na distância (Haversine)"""
    import math

    dados = request.get_json()
    cliente_lat = dados.get("lat")
    cliente_lng = dados.get("lng")

    if cliente_lat is None or cliente_lng is None:
        return jsonify({"sucesso": False, "erro": "Coordenadas não informadas!"})

    rest_lat = Config.RESTAURANTE_LAT
    rest_lng = Config.RESTAURANTE_LNG

    # Fórmula de Haversine
    R = 6371  # Raio da Terra em km
    dlat = math.radians(cliente_lat - rest_lat)
    dlng = math.radians(cliente_lng - rest_lng)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(rest_lat)) * math.cos(math.radians(cliente_lat)) *
         math.sin(dlng / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    distancia_km = R * c

    frete = round(distancia_km * Config.FRETE_POR_KM, 2)

    # Frete mínimo
    if frete < Config.FRETE_POR_KM:
        frete = Config.FRETE_POR_KM

    return jsonify({
        "sucesso": True,
        "distancia_km": round(distancia_km, 2),
        "frete": frete
    })


@app.route("/carrinho")
def carrinho_cliente():
    return render_template("carrinho_cliente.html")

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
