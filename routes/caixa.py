from datetime import datetime
from flask import Blueprint, render_template, jsonify, request, session
from data.db import get_connection, is_mysql
from helpers import get_restaurante_id_or_403, get_pagination_params, _get_sessao_inicio, caixa_or_admin_required, registrar_auditoria

caixa_bp = Blueprint('caixa', __name__)


@caixa_bp.route("/caixa")
@caixa_or_admin_required
def caixa():
    """Página do módulo de caixa"""
    return render_template("caixa.html")


@caixa_bp.route("/api/caixa/resumo")
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
        rid = get_restaurante_id_or_403()

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

        sessao_inicio = _get_sessao_inicio(cursor, rid)

        cursor.execute("""
            SELECT COUNT(*) as qtd, COALESCE(SUM(total), 0) as total,
                   COALESCE(SUM(taxa_entrega), 0) as taxa_total
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


@caixa_bp.route("/api/caixa/movimentacoes")
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
        rid = get_restaurante_id_or_403()
        page, per_page = get_pagination_params()

        sessao_inicio = _get_sessao_inicio(cursor, rid)
        movimentacoes = []

        def get_val(row, key, idx):
            if isinstance(row, dict): return row.get(key)
            return row[idx] if row and len(row) > idx else None

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
                "descricao": f"Pedido #{get_val(row, 'id', 0)} \u2014 {get_val(row, 'cliente_nome', 1)}",
                "valor": float(get_val(row, 'total', 2) or 0),
                "hora": get_val(row, 'criado_em', 3)
            })

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

        movimentacoes.sort(key=lambda x: x["hora"] or "", reverse=True)
        total = len(movimentacoes)
        inicio = (page - 1) * per_page
        movimentacoes = movimentacoes[inicio:inicio + per_page]

        return jsonify({"sucesso": True, "movimentacoes": movimentacoes, "page": page, "per_page": per_page, "total": total})
    except Exception as e:
        import traceback
        error_msg = traceback.format_exc()
        with open("caixa_error.log", "a", encoding="utf-8") as f:
            f.write(f"\n--- [MOVIMENTACOES] {datetime.now()} ---\n{error_msg}\n")
        print(f"Erro em /api/caixa/movimentacoes:\n{error_msg}")
        return jsonify({"sucesso": False, "erro": str(e)}), 200


@caixa_bp.route("/api/caixa/fechar", methods=["POST"])
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
        rid = get_restaurante_id_or_403()

        cursor.execute("""
            SELECT id FROM caixa_fechamentos
            WHERE data = DATE('now', 'localtime')
            AND restaurante_id = ?
        """, (rid,))
        if cursor.fetchone():
            db.close()
            return jsonify({"sucesso": False, "erro": "Caixa j\u00e1 foi fechado hoje!"})

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

        cursor.execute("""
            UPDATE pedidos_delivery
            SET status = 'fechado'
            WHERE criado_em >= ?
            AND status = 'entregue'
            AND restaurante_id = ?
        """, (sessao_inicio, rid))

        db.commit()
        db.close()

        registrar_auditoria('fechar_caixa', table_name='fechamentos_caixa', record_id=rid, detalhes={
            'total_geral': total_geral, 'total_delivery': d_total, 'total_mesas': m_total
        })

        return jsonify({
            "sucesso": True,
            "total_delivery": d_total,
            "total_mesas": m_total,
            "total_geral": total_geral
        })
    except Exception as e:
        print(f"Erro em fechar_caixa: {e}")
        return jsonify({"sucesso": False, "erro": str(e)}), 500


@caixa_bp.route("/api/caixa/historico")
@caixa_or_admin_required
def caixa_historico():
    """Retorna fechamentos da tabela fechamentos_caixa filtrados por m\u00eas/ano"""
    try:
        mes = request.args.get("mes", "01").zfill(2)
        ano = request.args.get("ano", "2026")
        rid = get_restaurante_id_or_403()
        page, per_page = get_pagination_params()

        db = get_connection()
        if not is_mysql():
            import sqlite3
            db.row_factory = sqlite3.Row
        else:
            db.row_factory = True
        cursor = db.cursor()

        ph = "%s" if is_mysql() else "?"

        if is_mysql():
            cursor.execute("""
                SELECT COUNT(*) FROM fechamentos_caixa
                WHERE MONTH(data) = %s AND YEAR(data) = %s
                AND restaurante_id = %s
            """, (mes, ano, rid))
        else:
            cursor.execute("""
                SELECT COUNT(*) FROM fechamentos_caixa
                WHERE strftime('%%m', data) = ? AND strftime('%%Y', data) = ?
                AND restaurante_id = ?
            """, (mes, ano, rid))
        total = cursor.fetchone()[0]

        offset = (page - 1) * per_page

        if is_mysql():
            cursor.execute(f"""
                SELECT data, total_faturado, total_pedidos, total_entregas, valor_entregas
                FROM fechamentos_caixa
                WHERE MONTH(data) = %s AND YEAR(data) = %s
                AND restaurante_id = %s
                ORDER BY data ASC
                LIMIT %s OFFSET %s
            """, (mes, ano, rid, per_page, offset))
        else:
            cursor.execute(f"""
                SELECT data, total_faturado, total_pedidos, total_entregas, valor_entregas
                FROM fechamentos_caixa
                WHERE strftime('%%m', data) = ? AND strftime('%%Y', data) = ?
                AND restaurante_id = ?
                ORDER BY data ASC
                LIMIT ? OFFSET ?
            """, (mes, ano, rid, per_page, offset))

        fechamentos = [dict(row) for row in cursor.fetchall()]
        db.close()

        total_faturado = sum(float(f["total_faturado"]) for f in fechamentos)
        total_pedidos = sum(int(f["total_pedidos"]) for f in fechamentos)
        total_entregas = sum(int(f["total_entregas"]) for f in fechamentos)
        valor_entregas = sum(float(f["valor_entregas"]) for f in fechamentos)

        return jsonify({
            "sucesso": True,
            "fechamentos": fechamentos,
            "page": page,
            "per_page": per_page,
            "total": total,
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


@caixa_bp.route("/api/caixa/abrir", methods=["POST"])
@caixa_or_admin_required
def abrir_caixa():
    """Reabre o caixa removendo o registro de fechamento e inicia nova sess\u00e3o"""
    try:
        rid = get_restaurante_id_or_403()
        db = get_connection()
        cursor = db.cursor()

        if is_mysql():
            cursor.execute("""
                DELETE FROM caixa_fechamentos
                WHERE DATE(fechado_em) = CURDATE()
                AND restaurante_id = %s
            """, (rid,))
            cursor.execute("INSERT INTO caixa_sessoes (aberto_em, restaurante_id) VALUES (NOW(), %s)", (rid,))
        else:
            cursor.execute("""
                DELETE FROM caixa_fechamentos
                WHERE DATE(fechado_em, 'localtime') = DATE('now', 'localtime')
                AND restaurante_id = ?
            """, (rid,))
            cursor.execute("INSERT INTO caixa_sessoes (aberto_em, restaurante_id) VALUES (CURRENT_TIMESTAMP, ?)", (rid,))

        db.commit()
        db.close()
        return jsonify({"sucesso": True})
    except Exception as e:
        print(f"Erro em abrir_caixa: {e}")
        return jsonify({"sucesso": False, "erro": str(e)}), 500


@caixa_bp.route("/api/caixa/balanco")
@caixa_or_admin_required
def caixa_balanco():
    """Retorna balan\u00e7o mensal agrupado por dia"""
    try:
        mes = request.args.get("mes", "01").zfill(2)
        ano = request.args.get("ano", "2026")
        rid = get_restaurante_id_or_403()
        page, per_page = get_pagination_params()

        db = get_connection()
        if not is_mysql():
            import sqlite3
            db.row_factory = sqlite3.Row
        else:
            db.row_factory = True
        cursor = db.cursor()

        ph = "%s" if is_mysql() else "?"

        where_month = "MONTH(criado_em)" if is_mysql() else "strftime('%m', criado_em)"
        where_year = "YEAR(criado_em)" if is_mysql() else "strftime('%Y', criado_em)"

        cursor.execute(f"""
            SELECT COUNT(*) FROM caixa_fechamentos
            WHERE {where_month} = {ph}
            AND {where_year} = {ph}
            AND restaurante_id = {ph}
        """, (mes, ano, rid))
        total = cursor.fetchone()[0]

        offset = (page - 1) * per_page

        cursor.execute(f"""
            SELECT DATE(criado_em) as data, total_delivery, total_mesas, total_geral,
                   qtd_pedidos_delivery, qtd_mesas, fechado_por
            FROM caixa_fechamentos
            WHERE {where_month} = {ph}
            AND {where_year} = {ph}
            AND restaurante_id = {ph}
            ORDER BY criado_em ASC
            LIMIT {ph} OFFSET {ph}
        """, (mes, ano, rid, per_page, offset))

        dias = [dict(row) for row in cursor.fetchall()]

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
            "page": page,
            "per_page": per_page,
            "total": total,
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
