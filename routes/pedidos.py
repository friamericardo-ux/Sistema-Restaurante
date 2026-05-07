import json
from flask import Blueprint, render_template, jsonify, request, session, redirect, url_for, current_app
from data.db import get_connection, is_mysql
from repository import criar_pedido_delivery
from helpers import get_restaurante_id_or_403, get_pagination_params, _get_rid_from_slug, get_status_restaurante, registrar_auditoria, login_required, _get_sessao_inicio
from extensions import csrf, limiter

pedidos_bp = Blueprint('pedidos', __name__)


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
        resumo += f"  \u2022 {qtd}x {nome} - R$ {preco:.2f}\n"

    resumo += f"""
🛵 Taxa de entrega: R$ {taxa_entrega:.2f}
💰 TOTAL: R$ {total:.2f}

⏱️ Tempo estimado: 40 a 50 minutos

Obrigado pela preferência! \U0001f389
"""
    return resumo.strip()


@pedidos_bp.route("/api/pedido", methods=["POST"])
@csrf.exempt
@limiter.limit("60/minute")
def route_criar_pedido():
    """Cria um novo pedido delivery"""
    try:
        dados = request.get_json()
        slug = (dados.get("slug") or "").strip()
        restaurante_id = _get_rid_from_slug(slug)
        if not restaurante_id:
            return jsonify({"sucesso": False, "erro": "slug invalido ou ausente"}), 400
        if get_status_restaurante(restaurante_id) == "fechado":
            return jsonify({"sucesso": False, "erro": "Restaurante está fechado no momento"}), 403
        dados['restaurante_id'] = restaurante_id
        resultado = criar_pedido_delivery(dados)

        resumo = gerar_resumo_pedido(
            resultado["pedido_id"],
            resultado["cliente"],
            resultado["itens"],
            resultado["total"],
            resultado["taxa_entrega"]
        )

        registrar_auditoria('criar_pedido', table_name='pedidos', record_id=resultado["pedido_id"])

        return jsonify({
            "sucesso": True,
            "pedido_id": resultado["pedido_id"],
            "resumo": resumo
        })
    except Exception as e:
        current_app.logger.error(f"Erro no criar_pedido: {e}")
        return jsonify({"sucesso": False, "erro": "Erro ao criar pedido"}), 500


@pedidos_bp.route("/api/pedidos/delivery")
@login_required
def listar_pedidos_delivery():
    """Retorna pedidos delivery ativos + entregues hoje (por sessão de caixa)"""
    db = get_connection()
    cursor = db.cursor()
    rid = get_restaurante_id_or_403()
    ph = "%s" if is_mysql() else "?"
    page, per_page = get_pagination_params()

    sessao_inicio = _get_sessao_inicio(cursor, rid)

    cursor.execute(
        f"""SELECT id, cliente_nome, cliente_telefone, cliente_endereco,
                   itens, total, status, criado_em
            FROM pedidos_delivery
            WHERE restaurante_id = {ph}
            AND status NOT IN ('cancelado', 'rejeitado', 'entregue')
            ORDER BY criado_em DESC""",
        (rid,)
    )
    cols = [c[0] for c in cursor.description]
    pedidos = [dict(zip(cols, row)) for row in cursor.fetchall()]

    if sessao_inicio:
        cursor.execute(
            f"""SELECT COUNT(*) FROM pedidos_delivery
                WHERE restaurante_id = {ph}
                AND status = 'entregue'
                AND criado_em >= {ph}""",
            (rid, sessao_inicio)
        )
        total_entregues = cursor.fetchone()[0]
        offset = (page - 1) * per_page
        cursor.execute(
            f"""SELECT id, cliente_nome, cliente_telefone, cliente_endereco,
                       itens, total, status, criado_em
                FROM pedidos_delivery
                WHERE restaurante_id = {ph}
                AND status = 'entregue'
                AND criado_em >= {ph}
                ORDER BY criado_em DESC
                LIMIT {ph} OFFSET {ph}""",
            (rid, sessao_inicio, per_page, offset)
        )
    else:
        cursor.execute(
            f"""SELECT COUNT(*) FROM pedidos_delivery
                WHERE restaurante_id = {ph}
                AND status = 'entregue'
                AND DATE(criado_em) = CURDATE()""",
            (rid,)
        )
        total_entregues = cursor.fetchone()[0]
        offset = (page - 1) * per_page
        cursor.execute(
            f"""SELECT id, cliente_nome, cliente_telefone, cliente_endereco,
                       itens, total, status, criado_em
                FROM pedidos_delivery
                WHERE restaurante_id = {ph}
                AND status = 'entregue'
                AND DATE(criado_em) = CURDATE()
                ORDER BY criado_em DESC
                LIMIT {ph} OFFSET {ph}""",
            (rid, per_page, offset)
        )

    cols = [c[0] for c in cursor.description]
    entregues = [dict(zip(cols, row)) for row in cursor.fetchall()]
    db.close()

    for p in pedidos + entregues:
        p["itens"] = json.loads(p["itens"]) if p.get("itens") else []
        if p.get("criado_em") and hasattr(p["criado_em"], "isoformat"):
            p["criado_em"] = p["criado_em"].isoformat()

    return jsonify({"sucesso": True, "pedidos": pedidos + entregues, "page": page, "per_page": per_page, "total": total_entregues})


@pedidos_bp.route("/api/pedido/status", methods=["POST"])
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
    ph = "%s" if is_mysql() else "?"
    rid = get_restaurante_id_or_403()
    cursor.execute(
        f"UPDATE pedidos_delivery SET status = {ph} WHERE id = {ph} AND restaurante_id = {ph}",
        (novo_status, pedido_id, rid)
    )
    db.commit()
    db.close()

    return jsonify({"sucesso": True})


@pedidos_bp.route("/pedido/<int:id>/cancelar", methods=["POST"])
@csrf.exempt
@login_required
def cancelar_pedido(id):
    db = get_connection()
    cursor = db.cursor()
    ph = "%s" if is_mysql() else "?"
    rid = get_restaurante_id_or_403()
    cursor.execute(
        f"UPDATE pedidos_delivery SET status = 'cancelado' WHERE id = {ph} AND status = 'novo' AND restaurante_id = {ph}",
        (id, rid)
    )
    alterado = cursor.rowcount
    db.commit()
    db.close()

    if alterado == 0:
        return jsonify({"sucesso": False, "erro": "Pedido não encontrado ou não está como 'novo'."})
    return jsonify({"sucesso": True})
