import math
from flask import Blueprint, render_template, jsonify, request
from config import Config
from helpers import get_config, login_required
from extensions import csrf, limiter

delivery_bp = Blueprint('delivery', __name__)


@delivery_bp.route("/delivery")
@login_required
def painel_delivery():
    """Página do painel de pedidos delivery"""
    return render_template("painel_delivery.html")


@delivery_bp.route("/api/maps/calcular-frete", methods=["POST"])
@csrf.exempt
@limiter.limit("30/minute")
def calcular_frete():
    """Calcula frete via Distance Matrix API com fallback Haversine"""
    import requests as http_requests

    dados = request.get_json()
    cliente_lat = dados.get("lat")
    cliente_lng = dados.get("lng")
    endereco_destino = dados.get("endereco_destino")
    rid = dados.get("restaurante_id", 1)

    if endereco_destino is None and (cliente_lat is None or cliente_lng is None):
        return jsonify({"sucesso": False, "erro": "Coordenadas n\u00e3o informadas!"})

    frete_por_km = float(get_config("frete_por_km", Config.FRETE_POR_KM, restaurante_id=rid))
    google_maps_key = Config.GOOGLE_MAPS_KEY
    rest_lat = float(get_config("restaurante_lat", Config.RESTAURANTE_LAT, restaurante_id=rid))
    rest_lng = float(get_config("restaurante_lng", Config.RESTAURANTE_LNG, restaurante_id=rid))

    destinations = endereco_destino if endereco_destino else f"{cliente_lat},{cliente_lng}"

    distancia_km = None

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
        return jsonify({"sucesso": False, "erro": "N\u00e3o foi poss\u00edvel calcular a dist\u00e2ncia!"})

    frete = round(distancia_km * frete_por_km, 2)

    return jsonify({"sucesso": True, "frete": frete, "distancia_km": round(distancia_km, 2)})
