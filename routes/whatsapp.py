import requests as http_requests
from flask import Blueprint, render_template, jsonify, request, session, current_app
from config import Config
from data.db import get_connection, is_mysql
from helpers import get_restaurante_id_or_403, get_config, login_required
from repository import WhatsappRepository
from extensions import csrf, limiter

whatsapp_bp = Blueprint('whatsapp_bp', __name__, url_prefix='/whatsapp')

EVOLUTION_API_URL = Config.EVOLUTION_API_URL.rstrip('/')
EVOLUTION_API_KEY = Config.EVOLUTION_API_KEY


def _evolution_headers():
    return {
        "apikey": EVOLUTION_API_KEY,
        "Content-Type": "application/json"
    }


def _get_instance_name():
    rid = get_restaurante_id_or_403()
    repo = WhatsappRepository(rid)
    config = repo.get_config()
    if config:
        try:
            return config['instance_name']
        except (TypeError, KeyError):
            return config[2] if len(config) > 2 else 'pantanal-burger'
    return get_config("evolution_instance_name", "pantanal-burger", restaurante_id=rid)


@whatsapp_bp.route("/")
@login_required
def index():
    return render_template("whatsapp/index.html")


def _get_robo_enabled(rid):
    repo = WhatsappRepository(rid)
    config = repo.get_config()
    if config:
        try:
            return bool(config['enabled'])
        except (TypeError, KeyError):
            return bool(config[4]) if len(config) > 4 else False
    return get_config("robo_enabled", "0", restaurante_id=rid) == "1"


@whatsapp_bp.route("/status")
@login_required
def status():
    rid = get_restaurante_id_or_403()
    instance = _get_instance_name()
    robo_enabled = _get_robo_enabled(rid)
    try:
        resp = http_requests.get(
            f"{EVOLUTION_API_URL}/instance/connectionState/{instance}",
            headers=_evolution_headers(),
            timeout=10
        )
        data = resp.json()
        instance_state = data.get("instance", {})
        state_value = instance_state.get("state") or data.get("state", "")
        connected = state_value == "open"
        return jsonify({
            "sucesso": True,
            "connected": connected,
            "enabled": robo_enabled,
            "instance": instance,
            "state": state_value
        })
    except Exception as e:
        current_app.logger.error(f"Evolution status error: {e}")
        return jsonify({
            "sucesso": False,
            "connected": False,
            "enabled": _get_robo_enabled(rid),
            "erro": str(e)
        })


@whatsapp_bp.route("/qrcode")
@login_required
def qrcode():
    instance = _get_instance_name()
    try:
        resp = http_requests.get(
            f"{EVOLUTION_API_URL}/instance/qrcode/{instance}",
            headers=_evolution_headers(),
            timeout=10
        )
        data = resp.json()
        qrcode_base64 = (
            data.get("qrcode", {}).get("base64")
            or data.get("base64")
            or data.get("qrcode")
        )
        return jsonify({
            "sucesso": True,
            "qrcode": qrcode_base64,
            "instance": instance
        })
    except Exception as e:
        current_app.logger.error(f"Evolution qrcode error: {e}")
        return jsonify({
            "sucesso": False,
            "qrcode": None,
            "erro": str(e)
        })


@whatsapp_bp.route("/config")
@login_required
def config_get():
    rid = get_restaurante_id_or_403()
    repo = WhatsappRepository(rid)
    row = repo.get_config()
    if row:
        try:
            data = {
                "instance_name": row["instance_name"],
                "webhook_url": row["webhook_url"],
                "enabled": bool(row["enabled"])
            }
        except (TypeError, KeyError):
            data = {
                "instance_name": row[2],
                "webhook_url": row[3],
                "enabled": bool(row[4])
            }
    else:
        data = {
            "instance_name": get_config("evolution_instance_name", "pantanal-burger", restaurante_id=rid),
            "webhook_url": "",
            "enabled": get_config("robo_enabled", "0", restaurante_id=rid) == "1"
        }
    return jsonify({"sucesso": True, "config": data})


@whatsapp_bp.route("/config", methods=["POST"])
@csrf.exempt
@login_required
def config_set():
    rid = get_restaurante_id_or_403()
    repo = WhatsappRepository(rid)
    repo.upsert_config(
        instance_name=request.json.get("instance_name"),
        webhook_url=request.json.get("webhook_url")
    )
    return jsonify({"sucesso": True})


@whatsapp_bp.route("/toggle", methods=["POST"])
@csrf.exempt
@login_required
def toggle():
    rid = get_restaurante_id_or_403()
    repo = WhatsappRepository(rid)
    current_enabled = _get_robo_enabled(rid)
    repo.upsert_config(enabled=not current_enabled)
    return jsonify({
        "sucesso": True,
        "enabled": not current_enabled
    })


@whatsapp_bp.route("/instance/create", methods=["POST"])
@csrf.exempt
@login_required
def instance_create():
    rid = get_restaurante_id_or_403()
    db = get_connection()
    cursor = db.cursor()
    ph = "%s" if is_mysql() else "?"

    cursor.execute(f"SELECT slug FROM restaurantes WHERE id = {ph}", (rid,))
    row = cursor.fetchone()
    db.close()

    if not row:
        return jsonify({"sucesso": False, "erro": "Restaurant not found"}), 404

    slug = row[0] if not isinstance(row, dict) else row.get("slug", "")
    if not slug:
        return jsonify({"sucesso": False, "erro": "Restaurant has no slug"}), 400

    instance_name = f"{slug}-bot"

    try:
        resp = http_requests.post(
            f"{EVOLUTION_API_URL}/instance/create",
            headers=_evolution_headers(),
            json={"instanceName": instance_name, "qrcode": True},
            timeout=30
        )
        data = resp.json()

        if resp.status_code >= 400:
            return jsonify({
                "sucesso": False,
                "erro": data.get("error") or data.get("message") or "Evolution API error"
            }), 400

        repo = WhatsappRepository(rid)
        repo.upsert_config(instance_name=instance_name)

        qrcode_base64 = (
            data.get("qrcode", {}).get("base64")
            or data.get("base64")
            or data.get("qrcode")
        )

        return jsonify({
            "sucesso": True,
            "instance": instance_name,
            "qrcode": qrcode_base64
        })
    except Exception as e:
        current_app.logger.error(f"Evolution instance create error: {e}")
        return jsonify({
            "sucesso": False,
            "erro": str(e)
        }), 500
