import requests as http_requests
from flask import Blueprint, render_template, jsonify, request, session, current_app
from config import Config
from helpers import get_restaurante_id_or_403, get_config, set_config, login_required
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
    return get_config("evolution_instance_name", "pantanal-burger", restaurante_id=rid)


@whatsapp_bp.route("/")
@login_required
def index():
    return render_template("whatsapp/index.html")


@whatsapp_bp.route("/status")
@login_required
def status():
    rid = get_restaurante_id_or_403()
    instance = _get_instance_name()
    robo_enabled = get_config("robo_enabled", "0", restaurante_id=rid) == "1"
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
        robo_enabled = get_config("robo_enabled", "0", restaurante_id=rid) == "1"
        return jsonify({
            "sucesso": False,
            "connected": False,
            "enabled": robo_enabled,
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


@whatsapp_bp.route("/toggle", methods=["POST"])
@csrf.exempt
@login_required
def toggle():
    rid = get_restaurante_id_or_403()
    current_val = get_config("robo_enabled", "0", restaurante_id=rid)
    new_val = "0" if current_val == "1" else "1"
    set_config("robo_enabled", new_val, restaurante_id=rid)
    return jsonify({
        "sucesso": True,
        "enabled": new_val == "1"
    })
