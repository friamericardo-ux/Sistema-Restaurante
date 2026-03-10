"""Reescreve templates/admin_adicionais.html com herança de base.html (sem CSS inline)."""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET = os.path.join(ROOT, "templates", "admin_adicionais.html")

NEW_CONTENT = """\
{% extends "base.html" %}

{% block title %}Admin &mdash; Adicionais{% endblock %}

{% block extra_css %}
<link rel="stylesheet" href="{{ url_for('static', filename='css/admin.css') }}">
{% endblock %}

{% block content %}
<div class="header">
  <h1>&#9881;&#65039; Admin &mdash; Adicionais</h1>
  <nav class="nav-links">
    <a href="/admin/produtos">Produtos</a>
    <a href="/admin/adicionais" class="active">Adicionais</a>
    <a href="/">Mesas</a>
    <a href="/logout">Sair</a>
  </nav>
</div>

<div class="container">

  <div class="form-box">
    <h2>&#10133; Novo Adicional</h2>
    <form method="POST" action="/admin/adicionais/adicionar">
      <div class="form-row">
        <div class="form-group">
          <label>Nome do adicional</label>
          <input type="text" name="nome" placeholder="Ex: Bacon, Queijo extra..." required>
        </div>
        <div class="form-group" style="max-width:140px;">
          <label>Pre&ccedil;o (R$)</label>
          <input type="number" name="preco" step="0.01" min="0" placeholder="3.00" required>
        </div>
        <button type="submit" class="btn-add">Adicionar</button>
      </div>
    </form>
  </div>

  <div class="section-label">&#128203; Adicionais cadastrados</div>

  <div class="adicional-list">
    {% if adicionais %}
      {% for a in adicionais %}
      <div class="adicional-item">
        <div class="adicional-info">
          <span class="adicional-nome">{{ a[1] }}</span>
          <span class="adicional-preco">+R$ {{ "%.2f"|format(a[2]) }}</span>
        </div>
        <a href="/admin/adicionais/desativar/{{ a[0] }}" class="btn-remover"
           onclick="return confirm('Remover {{ a[1] }}?')">Remover</a>
      </div>
      {% endfor %}
    {% else %}
      <div class="empty">Nenhum adicional cadastrado ainda.</div>
    {% endif %}
  </div>

</div>
{% endblock %}
"""

with open(TARGET, "w", encoding="utf-8") as f:
    f.write(NEW_CONTENT)

print(f"✅ admin_adicionais.html reescrito! Linhas: {NEW_CONTENT.count(chr(10))}")
