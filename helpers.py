import json
from datetime import datetime
from functools import wraps
from data.db import get_connection, is_mysql


def get_restaurante_id_or_403():
    from flask import session, abort
    role = session.get('role')
    restaurante_id = session.get('restaurante_id')
    if restaurante_id is None:
        if role not in ('superadmin', 'super_admin'):
            abort(403)
        return None
    return int(restaurante_id)


def get_pagination_params():
    from flask import request
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    page = max(page, 1)
    per_page = max(min(per_page, 200), 1)
    return page, per_page


def get_config(chave, fallback=None, restaurante_id=1):
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


def get_status_restaurante(restaurant_id):
    horario_abertura = get_config("horario_abertura", "18:00", restaurante_id=restaurant_id)
    horario_fechamento = get_config("horario_fechamento", "23:00", restaurante_id=restaurant_id)
    dias_funcionamento = get_config("dias_funcionamento", "", restaurante_id=restaurant_id)
    restaurante_ativo = get_config("restaurante_ativo", "1", restaurante_id=restaurant_id)

    if restaurante_ativo == "0":
        return "fechado"

    try:
        import zoneinfo
        tz = zoneinfo.ZoneInfo("America/Sao_Paulo")
    except ImportError:
        from datetime import timezone, timedelta
        tz = timezone(timedelta(hours=-3))

    agora = datetime.now(tz)
    hora_agora = agora.time()

    dias_abertos = parsear_dias(dias_funcionamento)
    dia_hoje = DIAS_ORDEM[agora.weekday()] if agora.weekday() < len(DIAS_ORDEM) else ""
    if not dias_abertos or dia_hoje not in dias_abertos:
        return "fechado"

    try:
        abertura = datetime.strptime(horario_abertura, "%H:%M").time()
        fechamento = datetime.strptime(horario_fechamento, "%H:%M").time()
        if abertura <= fechamento:
            return "aberto" if abertura <= hora_agora <= fechamento else "fechado"
        return "aberto" if hora_agora >= abertura or hora_agora <= fechamento else "fechado"
    except Exception:
        return "fechado"


def verificar_horario_funcionamento(restaurant_id):
    agora_dt = datetime.now()
    chave = f"status_{restaurant_id}"
    ultima = _ultima_verificacao_status.get(chave)
    if ultima and (agora_dt - ultima).total_seconds() < 300:
        return

    try:
        novo_status = get_status_restaurante(restaurant_id)
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


def _get_rid_from_slug(slug):
    if not slug:
        return None
    db = get_connection()
    cursor = db.cursor()
    cursor.execute("SELECT id FROM restaurantes WHERE slug = %s AND ativo = 1", (slug,))
    row = cursor.fetchone()
    db.close()
    return row[0] if row else None


def _get_sessao_inicio(cursor, restaurante_id=1):
    """Retorna o datetime de início da sessão atual do caixa como string."""
    from data.db import is_mysql
    from datetime import datetime, date
    if is_mysql():
        cursor.execute(
            "SELECT aberto_em FROM caixa_sessoes WHERE DATE(aberto_em) = CURDATE() AND restaurante_id = %s ORDER BY aberto_em DESC LIMIT 1",
            (restaurante_id,)
        )
    else:
        cursor.execute(
            "SELECT aberto_em FROM caixa_sessoes WHERE DATE(aberto_em, 'localtime') = DATE('now', 'localtime') AND restaurante_id = ? ORDER BY aberto_em DESC LIMIT 1",
            (restaurante_id,)
        )
    row = cursor.fetchone()
    if row:
        try:
            aberto_em = row['aberto_em']
        except (TypeError, KeyError):
            aberto_em = row[0]
        if hasattr(aberto_em, 'strftime'):
            return aberto_em.strftime('%Y-%m-%d %H:%M:%S')
        return aberto_em
    hoje = date.today()
    return datetime(hoje.year, hoje.month, hoje.day, 0, 0, 0).strftime('%Y-%m-%d %H:%M:%S')


def login_required(f):
    from flask import session, redirect, url_for
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('auth.login_web'))
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    from flask import session, redirect, url_for
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('auth.login_web'))
        if session.get('role') not in ('admin', 'superadmin', 'super_admin'):
            return redirect(url_for('mesas.mesas'))
        return f(*args, **kwargs)
    return decorated_function


def caixa_or_admin_required(f):
    from flask import session, redirect, url_for
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('auth.login_web'))
        if session.get('role') not in ('admin', 'superadmin', 'super_admin', 'caixa'):
            return redirect(url_for('mesas.mesas'))
        return f(*args, **kwargs)
    return decorated


def superadmin_required(f):
    from flask import session, redirect, url_for
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get('role') not in ('superadmin', 'super_admin'):
            return redirect(url_for('auth.login_web'))
        if not session.get('superadmin_pin_ok'):
            return redirect(url_for('superadmin_pin'))
        return f(*args, **kwargs)
    return decorated


def registrar_auditoria(action, table_name=None, record_id=None, detalhes=None):
    from flask import session, request
    try:
        db = get_connection()
        cursor = db.cursor()
        ph = "%s" if is_mysql() else "?"
        cursor.execute(f"""
            INSERT INTO audit_logs
            (restaurante_id, user_id, action, table_name, record_id, ip_address, detalhes)
            VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph})
        """, (
            session.get('restaurante_id'),
            session.get('user_id'),
            action,
            table_name,
            record_id,
            request.remote_addr,
            json.dumps(detalhes) if detalhes else None
        ))
        db.commit()
        db.close()
    except Exception:
        pass

