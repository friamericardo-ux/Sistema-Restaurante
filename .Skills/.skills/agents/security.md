# Segurança e Código Limpo — Comanda Digital

> Skill aplicada pelo agente em TODA alteração de código.
> Projeto: Flask + MySQL + multi-tenant (restaurante_id) + Jinja2

---

## 1. Segurança (OWASP 2026)

### A01 — Broken Access Control (CRÍTICO para multi-tenant)

O maior risco do Comanda Digital é um restaurante acessar dados de outro.

**Regra obrigatória:** Toda query que busca dados de pedidos, mesas, produtos,
categorias ou usuários DEVE filtrar por `restaurante_id` da sessão.

```python
# ERRADO — qualquer restaurante vê qualquer pedido
pedido = db.session.query(Pedido).filter_by(id=pedido_id).first()

# CORRETO — garante isolamento do tenant
restaurante_id = session.get('restaurante_id')
pedido = db.session.query(Pedido).filter_by(
    id=pedido_id,
    restaurante_id=restaurante_id
).first()
if not pedido:
    abort(403)
```

**Regra obrigatória:** Toda rota do painel admin deve ter o decorator de login
verificando a sessão ativa. Nunca confie apenas no frontend.

```python
# Decorator padrão do projeto — use em TODAS as rotas admin
@login_required
@tenant_required  # garante restaurante_id na sessão
def minha_rota():
    ...
```

### A02 — IDs Sequenciais nas URLs

IDs numéricos sequenciais expõem quantos restaurantes/pedidos existem
e facilitam enumeração por atacantes.

**Regra:** Novas entidades (restaurantes, tokens de acesso público) usam UUID.
Entidades internas (pedidos, mesas) podem manter int por performance,
mas nunca expor em URLs públicas sem validação de tenant.

```python
import uuid
# Para criar token público de cardápio:
token_publico = str(uuid.uuid4())
```

### A03 — Validação de Entrada

Nunca processe dados do usuário sem validar. Use whitelist (o que é permitido),
não blacklist (o que é bloqueado).

```python
import re

# ERRADO — aceita qualquer coisa
nome_produto = request.form.get('nome')

# CORRETO — valida antes de usar
nome_produto = request.form.get('nome', '').strip()
if not re.match(r'^[\w\s\-\.áéíóúâêôãõçÁÉÍÓÚÂÊÔÃÕÇ]{2,100}$', nome_produto):
    return jsonify({'erro': 'Nome inválido'}), 400
```

**Campos e suas regras:**
- `nome` (produto, categoria): letras, números, espaços, acentos, 2–100 chars
- `preco`: Decimal, maior que 0, máximo 9999.99
- `telefone`: apenas dígitos, 10–11 chars
- `email`: validar com regex ou biblioteca
- `restaurante_id`: sempre vem da **sessão**, nunca do formulário

### A04 — Logs sem Dados Sensíveis

Nunca logar senhas, tokens ou dados de cartão.

```python
# ERRADO
app.logger.debug(f"Login: usuário={username} senha={password}")

# CORRETO
app.logger.info(f"Login bem-sucedido: usuário={username} restaurante_id={rid}")
```

### A05 — Configurações de Produção

Checklist obrigatório antes de qualquer deploy:

```python
# config.py — produção
SESSION_COOKIE_SECURE = True       # só HTTPS
SESSION_COOKIE_HTTPONLY = True     # bloqueia JS de ler o cookie
SESSION_COOKIE_SAMESITE = 'Lax'   # proteção CSRF básica
DEBUG = False                      # NUNCA True em produção
SECRET_KEY = os.environ['SECRET_KEY']  # nunca hardcoded
```

---

## 2. Clean Code — Padrões do Projeto

### Nomenclatura

- **Variáveis e funções:** inglês, snake_case, descritivos
- **Rotas Flask:** português nas URLs (`/admin/pedidos`), inglês no código Python
- **Evite:** `x`, `tmp`, `data`, `result` sem contexto

```python
# ERRADO
def get_data(id):
    r = db.session.query(Pedido).filter_by(id=id).first()
    return r

# CORRETO
def get_order_by_id(order_id: int, restaurant_id: int):
    order = db.session.query(Pedido).filter_by(
        id=order_id,
        restaurante_id=restaurant_id
    ).first()
    return order
```

### DRY — Não Repita Lógica

Se uma query ou validação aparece em mais de um lugar, vira função no
`repository.py` ou utilitário em `utils.py`.

```python
# repository.py — centraliza queries
def get_active_products(restaurant_id: int):
    """Retorna produtos ativos de um restaurante, ordenados por categoria."""
    return db.session.query(Produto).filter_by(
        restaurante_id=restaurant_id,
        ativo=True
    ).order_by(Produto.categoria_id).all()
```

### Comente o "Porquê", não o "O quê"

O código já diz o que faz. O comentário explica a decisão ou o contexto.

```python
# INÚTIL
# busca pedido
pedido = get_order_by_id(order_id, restaurant_id)

# ÚTIL — explica a decisão de negócio
# Delivery e mesa usam a mesma tabela de pedidos.
# O tipo é diferenciado pelo campo `canal` ('mesa', 'delivery', 'balcao').
pedido = get_order_by_id(order_id, restaurant_id)
```

### Tratamento de Erro Padrão

Toda rota usa try/except com logging. Nunca retorna traceback pro cliente.

```python
@app.route('/api/pedidos/delivery')
@login_required
def get_delivery_orders():
    try:
        restaurant_id = session.get('restaurante_id')
        orders = get_delivery_orders_by_restaurant(restaurant_id)
        return jsonify([o.to_dict() for o in orders])
    except Exception as e:
        app.logger.error(f"Erro em /api/pedidos/delivery: {e}", exc_info=True)
        return jsonify({'erro': 'Erro interno'}), 500
```

### Estrutura de Arquivos — Separação de Responsabilidades

```
app.py           → só rotas e handlers HTTP
repository.py    → todas as queries do banco (nunca SQL nas rotas)
services.py      → lógica de negócio (cálculos, regras)
utils.py         → funções auxiliares reutilizáveis
models.py        → definição das tabelas
```

**Regra:** Se a rota tem mais de 20 linhas, mova a lógica pro `services.py`.

---

## 3. Checklist do Agente

Antes de entregar qualquer código, verifique:

- [ ] Query filtra por `restaurante_id` da sessão?
- [ ] Rota tem `@login_required`?
- [ ] Entrada do usuário foi validada com whitelist?
- [ ] Erro capturado com try/except e logado?
- [ ] Nenhuma senha, token ou dado sensível nos logs?
- [ ] Lógica repetida foi extraída para função?
- [ ] Comentários explicam o "porquê" onde necessário?
-