# AGENTS.md — Diretrizes do Projeto Comanda Digital

> Este arquivo define as regras, padrões e contexto do projeto.
> Todo agente de IA ou desenvolvedor DEVE ler este arquivo antes de qualquer alteração.

---

## 📌 Visão Geral

**Comanda Digital** é um SaaS multi-tenant para gestão de restaurantes.
Cada restaurante é isolado por `restaurante_id`. Nenhuma query pode misturar dados entre restaurantes.

- **Domínio produção:** https://pantanaldev.com.br
- **Repositório:** github.com/friamericardo-ux/Sistema-Restaurante
- **Deploy:** Coolify v4 + Docker + Hetzner CPX22 (2 vCPU, 4GB RAM)

---

## 🏗️ Stack Técnica

| Camada | Tecnologia |
|---|---|
| Backend | Python 3.11 + Flask |
| Banco de dados | MySQL 8 (PyMySQL + SQLAlchemy) |
| Deploy | Docker + Coolify |
| Proxy/SSL | Traefik + Let's Encrypt |
| Frontend | HTML + CSS + JS (Jinja2 templates) |

---

## 📁 Estrutura de Pastas

```
/
├── app.py                  # Entrypoint Flask + rotas principais
├── repository.py           # Todas as queries ao banco de dados
├── migrations/             # Scripts SQL de migração (001, 002...)
├── static/
│   ├── css/                # Estilos — NÃO alterar sem pedido explícito
│   ├── js/                 # Scripts frontend
│   └── img/                # Imagens e uploads
├── templates/              # HTML Jinja2
├── .env                    # Variáveis locais — NUNCA commitar
├── AGENTS.md               # Este arquivo
└── requirements.txt        # Dependências Python
```

---

## 🔒 Regras de Segurança — OBRIGATÓRIAS

1. **NUNCA** commitar `.env` ou qualquer arquivo com credenciais
2. **NUNCA** expor `SECRET_KEY`, senhas de banco ou API keys no código
3. Senhas de usuário SEMPRE com `werkzeug.security` (hash bcrypt)
4. Toda rota autenticada DEVE verificar `session['user_id']` e `session['restaurante_id']`
5. `SESSION_COOKIE_SECURE=True` em produção
6. Inputs do usuário SEMPRE sanitizados antes de queries SQL

---

## 🏢 Regras de Multi-Tenancy — CRÍTICO

- Toda query DEVE filtrar por `restaurante_id`
- O `restaurante_id` vem sempre da sessão: `session['restaurante_id']`
- **NUNCA** retornar dados de um restaurante para outro
- Superadmin (`role='superadmin'`) pode ver todos — tratar separado

```python
# CORRETO
produtos = db.execute(
    "SELECT * FROM produtos WHERE restaurante_id = %s", 
    (session['restaurante_id'],)
)

# ERRADO — vaza dados entre restaurantes
produtos = db.execute("SELECT * FROM produtos")
```

---

## 🗄️ Banco de Dados

**Conexão:** MySQL via `DATABASE_URL` no ambiente (nunca hardcoded)

**Tabelas principais:**
- `restaurantes` — cadastro dos tenants
- `users` — com colunas: id, username, password_hash, role, restaurante_id
- `produtos` — cardápio por restaurante
- `adicionais` + `adicional_categoria` — extras dos produtos
- `pedidos_delivery` — pedidos com status e entregador
- `mesas` + `historico_mesas` — gestão de mesas
- `configuracoes` — configs por restaurante (taxa entrega, WhatsApp etc)
- `caixa_sessoes` + `caixa_fechamentos` — controle de caixa
- `clientes_cache` — cache de clientes por restaurante
- `schema_migrations` — controle de versão do banco

**Regras:**
- Migrations numeradas sequencialmente: `001_`, `002_`, etc.
- Toda nova tabela ou coluna = nova migration, nunca alterar migration existente
- Usar apenas MySQL — sem SQLite em produção

---

## 🐍 Padrões de Código Python

```python
# Estrutura padrão de rota Flask
@app.route('/admin/exemplo')
@login_required
def exemplo():
    try:
        restaurante_id = session['restaurante_id']
        dados = repository.buscar_dados(restaurante_id)
        return render_template('exemplo.html', dados=dados)
    except Exception as e:
        app.logger.error(f"Erro em /admin/exemplo: {e}")
        return jsonify({'erro': 'Erro interno'}), 500
```

- Toda lógica de banco vai em `repository.py` — não inline no `app.py`
- Usar `try/except` em toda rota
- Logar erros com `app.logger.error()` — não usar `print()` em produção
- Retornar JSON para rotas `/api/` e HTML para rotas de página

---

## 🎨 Frontend

- CSS já está definido e funcional — **não alterar** sem pedido explícito
- Templates Jinja2 em `/templates/`
- JS de polling do painel delivery em `static/js/painel.js`
- Não adicionar bibliotecas externas sem aprovação

---

## 🚀 Deploy e Ambiente

**Variáveis de ambiente obrigatórias no Coolify:**
```
DATABASE_URL=mysql+pymysql://mysql:SENHA@HOST:3306/default
SECRET_KEY=<chave forte gerada>
FLASK_ENV=production
```

**Fluxo de deploy:**
1. Push para `main` no GitHub
2. Coolify detecta e rebuilda automaticamente
3. Verificar logs no Coolify após deploy

**NUNCA** reiniciar containers manualmente sem saber o impacto.

---

## ✅ Checklist antes de qualquer alteração

- [ ] Li o AGENTS.md completo
- [ ] A mudança filtra por `restaurante_id`?
- [ ] Tem `try/except` na rota?
- [ ] Não estou alterando CSS sem pedido?
- [ ] Não estou commitando `.env`?
- [ ] Se mudou banco → criei migration nova?
- [ ] Testei localmente antes de sugerir o deploy?

---

## 🐛 Problemas conhecidos (atualizar conforme resolver)

- [ ] `/api/dashboard/resumo` retorna 500 — causa: query com erro ou tabela faltando
- [ ] `/admin/adicionais` retorna 500 — mesma causa provável
- [ ] Logs de DEBUG no `app.py` e `repository.py` — remover após estabilizar
- [ ] `SESSION_COOKIE_SECURE` desativado temporariamente — reativar após HTTPS estável

---

*Última atualização: 27/04/2026*
