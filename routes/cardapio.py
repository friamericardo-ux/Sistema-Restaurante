from flask import Blueprint, render_template, jsonify, request, session, redirect, url_for, current_app, abort
from data.db import get_connection, is_mysql
from repository import listar_produtos, listar_adicionais
from config import Config
from helpers import get_config, get_status_restaurante, verificar_horario_funcionamento, _get_rid_from_slug, get_restaurante_id_or_403
from extensions import limiter

cardapio_bp = Blueprint('cardapio', __name__)


@cardapio_bp.route("/cardapio")
@limiter.limit("120/minute")
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
    status_loja = get_status_restaurante(rid)
    horario_abertura = get_config('horario_abertura', '18:00', rid)
    horario_fechamento = get_config('horario_fechamento', '23:00', rid)
    dias_funcionamento = get_config('dias_funcionamento', '', rid)
    return render_template("cardapio_cliente.html",
        slug=None,
        restaurante_nome=get_config('nome_restaurante', 'Restaurante', rid),
        restaurante_id=rid,
        status_loja=status_loja,
        horario_abertura=horario_abertura,
        horario_fechamento=horario_fechamento,
        dias_funcionamento=dias_funcionamento,
        whatsapp_restaurante=get_config('whatsapp_restaurante', Config.WHATSAPP_RESTAURANTE, rid),
        google_maps_key=Config.GOOGLE_MAPS_KEY)


@cardapio_bp.route("/api/cardapio")
@limiter.limit("120/minute")
def api_cardapio():
    """Retorna os produtos do cardápio"""
    try:
        slug = request.args.get('slug', '').strip()
        if slug:
            rid = _get_rid_from_slug(slug)
        else:
            rid = get_restaurante_id_or_403()
        if not rid:
            return jsonify({"sucesso": False, "erro": "slug ou sessao necessaria"}), 400
        produtos = listar_produtos(rid)
        resultado = []
        for p in produtos:
            resultado.append({
                "id": p[0],
                "nome": p[1],
                "preco": float(p[2]),
                "categoria": p[3],
                "emoji": p[4] if p[4] else '\U0001f37d\ufe0f',
                "foto": p[5],
                "descricao": p[6] if p[6] else "",
            })
        return jsonify({"sucesso": True, "produtos": resultado})
    except Exception as e:
        current_app.logger.error(f"Erro no api_cardapio: {e}")
        return jsonify({"sucesso": False, "erro": "Erro ao carregar card\u00e1pio"}), 500


@cardapio_bp.route("/api/adicionais")
@limiter.limit("120/minute")
def api_adicionais():
    try:
        slug = request.args.get('slug', '').strip()
        if slug:
            rid = _get_rid_from_slug(slug)
        else:
            rid = get_restaurante_id_or_403()
        if not rid:
            return jsonify({"sucesso": False, "erro": "slug ou sessao necessaria"}), 400
        categoria = request.args.get('categoria', None)
        adicionais = listar_adicionais(rid, categoria=categoria)
        resultado = [{"id": a[0], "nome": a[1], "preco": float(a[2])} for a in adicionais]
        return jsonify({"sucesso": True, "adicionais": resultado})
    except Exception as e:
        current_app.logger.error(f"Erro no api_adicionais: {e}")
        return jsonify({"sucesso": False, "erro": "Erro ao carregar adicionais"}), 500


@cardapio_bp.route("/api/configuracoes")
@limiter.limit("120/minute")
def api_configuracoes():
    """Retorna configs públicas para o frontend do cliente."""
    slug = request.args.get('slug', '').strip()
    if slug:
        rid = _get_rid_from_slug(slug)
    else:
        rid = get_restaurante_id_or_403()
    if not rid:
        return jsonify({"sucesso": False, "erro": "slug ou sessao necessaria"}), 400
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


@cardapio_bp.route("/cardapio/<slug>")
@limiter.limit("120/minute")
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
    horario_abertura = get_config("horario_abertura", "18:00", restaurante_id)
    horario_fechamento = get_config("horario_fechamento", "23:00", restaurante_id)
    dias_funcionamento = get_config("dias_funcionamento", "", restaurante_id)
    status_loja = get_status_restaurante(restaurante_id)
    return render_template("cardapio_cliente.html", slug=slug, restaurante_nome=nome,
        restaurante_id=restaurante_id,
        status_loja=status_loja,
        horario_abertura=horario_abertura,
        horario_fechamento=horario_fechamento,
        dias_funcionamento=dias_funcionamento,
        whatsapp_restaurante=get_config('whatsapp_restaurante', Config.WHATSAPP_RESTAURANTE, restaurante_id),
        google_maps_key=Config.GOOGLE_MAPS_KEY)
