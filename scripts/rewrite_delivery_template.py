"""Reescreve templates/painel_delivery.html com herança de base.html (sem CSS/JS inline)."""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET = os.path.join(ROOT, "templates", "painel_delivery.html")

NEW_CONTENT = """\
{% extends "base.html" %}

{% block title %}Painel Delivery{% endblock %}

{% block extra_css %}
<link rel="stylesheet" href="{{ url_for('static', filename='css/delivery.css') }}">
{% endblock %}

{% block content %}
<header>
  <h1>&#128757; Painel <span>Delivery</span></h1>
  <div class="header-right">
    <div class="status-dot"></div>
    <span class="status-text" id="ultima-atualizacao">Atualizando...</span>
    <a href="/" class="btn-voltar">&larr; Mesas</a>
  </div>
</header>

<div class="colunas">
  <!-- NOVOS -->
  <div class="coluna coluna-novo">
    <div class="coluna-titulo">
      &#128276; Novos
      <span class="contador" id="count-novo">0</span>
    </div>
    <div class="lista-pedidos" id="lista-novo"></div>
  </div>

  <!-- EM PREPARO -->
  <div class="coluna coluna-preparo">
    <div class="coluna-titulo">
      &#127859; Em preparo
      <span class="contador" id="count-em_preparo">0</span>
    </div>
    <div class="lista-pedidos" id="lista-em_preparo"></div>
  </div>

  <!-- SAIU PARA ENTREGA -->
  <div class="coluna coluna-saiu">
    <div class="coluna-titulo">
      &#128757; Saiu para entrega
      <span class="contador" id="count-saiu_entrega">0</span>
    </div>
    <div class="lista-pedidos" id="lista-saiu_entrega"></div>
  </div>
</div>

<div id="toast"></div>
{% endblock %}

{% block extra_js %}
<script src="{{ url_for('static', filename='js/delivery.js') }}"></script>
{% endblock %}
"""

with open(TARGET, "w", encoding="utf-8") as f:
    f.write(NEW_CONTENT)

print(f"✅ painel_delivery.html reescrito! Linhas: {NEW_CONTENT.count(chr(10))}")
