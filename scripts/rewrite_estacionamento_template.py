"""Reescreve templates/estacionamento.html com herança de base.html (sem CSS/JS inline)."""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET = os.path.join(ROOT, "templates", "estacionamento.html")

NEW_CONTENT = """\
{% extends "base.html" %}

{% block title %}Estacionamento — Pedidos{% endblock %}

{% block extra_css %}
<link rel="stylesheet" href="{{ url_for('static', filename='css/estacionamento.css') }}">
{% endblock %}

{% block content %}
<header>
  <h1>&#9889; PEDIDOS &mdash; ESTACIONAMENTO</h1>
  <div id="relogio"></div>
</header>

<div id="grid">
  <div class="vazio">&#9203; Aguardando pedidos...</div>
</div>
{% endblock %}

{% block extra_js %}
<script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.7.2/socket.io.min.js"></script>
<script src="{{ url_for('static', filename='js/estacionamento.js') }}"></script>
{% endblock %}
"""

with open(TARGET, "w", encoding="utf-8") as f:
    f.write(NEW_CONTENT)

print(f"✅ estacionamento.html reescrito! Linhas: {NEW_CONTENT.count(chr(10))}")
