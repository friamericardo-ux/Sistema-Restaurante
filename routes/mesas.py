from flask import Blueprint, render_template, jsonify, request, session, current_app
from data.db import get_connection, is_mysql
from repository import listar_mesas_com_itens, abrir_mesa as repo_abrir_mesa, get_mesa
from helpers import get_restaurante_id_or_403, get_pagination_params, login_required
from extensions import csrf

mesas_bp = Blueprint('mesas', __name__)


@mesas_bp.route("/mesas")
@login_required
def mesas():
    """Página de gestão de mesas — design moderno com cards e status visual."""
    return render_template("admin_mesas.html")


@mesas_bp.route("/api/mesas")
@login_required
def listar_mesas():
    try:
        rid = get_restaurante_id_or_403()
        page, per_page = get_pagination_params()
        mesas = listar_mesas_com_itens(rid)
        total = len(mesas)
        inicio = (page - 1) * per_page
        mesas_pag = mesas[inicio:inicio + per_page]
        return jsonify({"sucesso": True, "mesas": mesas_pag, "page": page, "per_page": per_page, "total": total})
    except Exception as e:
        current_app.logger.error(f"Erro no listar_mesas: {e}")
        return jsonify({"sucesso": False, "erro": "Erro ao listar mesas"}), 500


@mesas_bp.route("/api/mesa/abrir", methods=["POST"])
@csrf.exempt
@login_required
def route_abrir_mesa():
    try:
        dados = request.get_json()
        num = str(dados.get("numero"))
        rid = get_restaurante_id_or_403()

        sucesso, erro = repo_abrir_mesa(num, rid)
        return jsonify({"sucesso": sucesso, "erro": erro})
    except Exception as e:
        current_app.logger.error(f"Erro no abrir_mesa: {e}")
        return jsonify({"sucesso": False, "erro": "Erro ao abrir mesa"}), 500


@mesas_bp.route("/admin/force_close_mesa/<int:mesa_id>")
@login_required
def force_close_mesa(mesa_id):
    """Fecha forçado de mesa corrompida"""
    try:
        rid = get_restaurante_id_or_403()
        db = get_connection()
        cursor = db.cursor()
        ph = "%s" if is_mysql() else "?"
        cursor.execute(f"DELETE FROM itens WHERE mesa_id = {ph} AND restaurante_id = {ph}", (mesa_id, rid))
        cursor.execute(f"DELETE FROM mesas WHERE id = {ph} AND restaurante_id = {ph}", (mesa_id, rid))
        db.commit()
        db.close()
        return jsonify({"sucesso": True})
    except Exception as e:
        current_app.logger.error(f"Erro no force_close_mesa: {e}")
        return jsonify({"sucesso": False, "erro": str(e)}), 500


@mesas_bp.route('/mesa/comanda/<numero>')
@login_required
def mesa_comanda(numero):
    from datetime import datetime
    db = get_connection()
    cursor = db.cursor()
    ph = "%s" if is_mysql() else "?"
    rid = get_restaurante_id_or_403()
    cursor.execute(f"SELECT id, numero, total, status FROM mesas WHERE numero = {ph} AND restaurante_id = {ph}", (numero, rid))
    mesa = cursor.fetchone()
    if not mesa:
        return "Mesa n\u00e3o encontrada", 404
    cursor.execute(f"SELECT id, nome, preco, quantidade, observacao FROM itens WHERE mesa_id = {ph} AND restaurante_id = {ph}", (mesa[0], rid))
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
        cliente_endereco="Sal\u00e3o",
        itens=itens,
        taxa_entrega=0,
        total=float(mesa[2]),
        forma_pagamento="",
        troco=0,
        status=mesa[3] if mesa[3] else "aberta",
        criado_em=datetime.now().strftime("%d/%m/%Y %H:%M"),
        nome_restaurante="Restaurante",
        tipo_pedido="mesa",
        mesa_numero=str(numero),
    )
