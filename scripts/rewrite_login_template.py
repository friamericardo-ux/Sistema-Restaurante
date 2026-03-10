"""Reescreve templates/login.html com herança de base.html (sem CSS inline)."""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET = os.path.join(ROOT, "templates", "login.html")

NEW_CONTENT = """\
{% extends "base.html" %}

{% block title %}Login — Comanda Digital{% endblock %}

{% block extra_css %}
<link rel="stylesheet" href="{{ url_for('static', filename='css/login.css') }}">
{% endblock %}

{% block content %}
<div class="login-container">
  <div class="login-logo">
    <div class="login-icon">🍔</div>
    <h1>Comanda Digital</h1>
    <p>Faça login para acessar o sistema</p>
  </div>

  {% if erro %}
  <div class="erro-box">&#9888; {{ erro }}</div>
  {% endif %}

  <form method="POST" action="/login" autocomplete="on">
    <div class="form-group">
      <label for="username">Usuário</label>
      <input type="text" id="username" name="username"
             placeholder="Digite seu usuário" required autocomplete="username">
    </div>
    <div class="form-group">
      <label for="password">Senha</label>
      <input type="password" id="password" name="password"
             placeholder="••••••••" required autocomplete="current-password">
    </div>
    <button type="submit" class="btn-login">Entrar</button>
  </form>
</div>
{% endblock %}
"""

with open(TARGET, "w", encoding="utf-8") as f:
    f.write(NEW_CONTENT)

print(f"✅ login.html reescrito com sucesso! Linhas: {NEW_CONTENT.count(chr(10))}")
