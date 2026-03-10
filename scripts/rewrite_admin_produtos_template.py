"""Reescreve templates/admin_produtos.html com herança de base.html (sem CSS inline)."""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET = os.path.join(ROOT, "templates", "admin_produtos.html")

NEW_CONTENT = """\
{% extends "base.html" %}

{% block title %}Admin &mdash; Produtos{% endblock %}

{% block extra_css %}
<link rel="stylesheet" href="{{ url_for('static', filename='css/admin.css') }}">
{% endblock %}

{% block content %}
<div class="header">
  <h1>&#128722; Admin &mdash; Produtos</h1>
  <nav class="nav-links">
    <a href="/admin/produtos" class="active">Produtos</a>
    <a href="/admin/adicionais">Adicionais</a>
    <a href="/">Mesas</a>
    <a href="/logout">Sair</a>
  </nav>
</div>

<div class="container">

  <!-- FORMULÁRIO ADICIONAR -->
  <div class="form-box">
    <h2>&#10133; Adicionar Produto</h2>
    <form action="/admin/produtos/adicionar" method="POST" enctype="multipart/form-data">
      <div class="form-row">
        <div class="form-group">
          <label>Nome do produto</label>
          <input type="text" name="nome" placeholder="Ex: X-Bacon" required>
        </div>
        <div class="form-group" style="max-width:130px;">
          <label>Pre&ccedil;o (R$)</label>
          <input type="number" name="preco" placeholder="15.90" step="0.01" required>
        </div>
        <div class="form-group">
          <label>Categoria</label>
          <input type="text" name="categoria" placeholder="Ex: Lanches" required>
        </div>
        <div class="form-group" style="max-width:110px;">
          <label>Emoji</label>
          <input type="text" name="emoji" placeholder="&#127828;">
        </div>
      </div>
      <div class="form-row" style="margin-top:10px;">
        <div class="form-group">
          <label>Descri&ccedil;&atilde;o (opcional)</label>
          <textarea name="descricao" placeholder="Ingredientes ou informa&ccedil;&otilde;es extras..." rows="2"></textarea>
        </div>
        <div class="form-group" style="max-width:200px;">
          <label>Foto</label>
          <input type="file" name="foto" accept="image/*">
        </div>
        <button type="submit" class="btn-add" style="align-self:flex-end;">+ Adicionar</button>
      </div>
    </form>
  </div>

  <!-- LISTA DE PRODUTOS -->
  <div class="section-label">&#128230; Produtos cadastrados</div>

  <table>
    <thead>
      <tr>
        <th>Foto</th>
        <th>&#127381;</th>
        <th>Nome</th>
        <th>Pre&ccedil;o</th>
        <th>Categoria</th>
        <th>Descri&ccedil;&atilde;o</th>
        <th>A&ccedil;&atilde;o</th>
      </tr>
    </thead>
    <tbody>
      {% for p in produtos %}
      <tr>
        <td>
          {% if p[6] and p[6] != '' %}
          <img src="/static/img/produtos/{{ p[6] }}" class="thumb" alt="Foto de {{ p[1] }}"
               onerror="this.onerror=null;this.src='https://via.placeholder.com/46?text=?'">
          {% else %}
          <span class="no-image">Sem foto</span>
          {% endif %}
        </td>
        <td><span class="prod-emoji">{{ p[4] }}</span></td>
        <td><strong>{{ p[1] }}</strong></td>
        <td class="prod-preco">R$ {{ "%.2f"|format(p[2]) }}</td>
        <td><span class="prod-categoria">{{ p[3] }}</span></td>
        <td class="prod-descricao">{{ p[7] if p[7] else '—' }}</td>
        <td>
          <a href="/admin/produtos/desativar/{{ p[0] }}"
             onclick="return confirm('Remover {{ p[1] }}?')">
            <button class="btn-del">Remover</button>
          </a>
        </td>
      </tr>
      {% endfor %}
    </tbody>
  </table>

</div>
{% endblock %}
"""

with open(TARGET, "w", encoding="utf-8") as f:
    f.write(NEW_CONTENT)

print(f"✅ admin_produtos.html reescrito! Linhas: {NEW_CONTENT.count(chr(10))}")
