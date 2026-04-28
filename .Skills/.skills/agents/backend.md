# Backend Python/Flask — Padrões do Comanda Digital

> Skill obrigatória para qualquer alteração em `app.py`, `repository.py`,
> `services.py`, `models.py` ou `utils.py`.
> Stack: Python 3.11 + Flask + SQLAlchemy + MySQL + multi-tenant por `restaurante_id`.

---

## 1. Filosofia Geral

Código profissional não é código complexo — é código que qualquer dev
consegue ler e modificar sem pedir explicação.

**Princípios que guiam este projeto:**
- Uma função faz uma coisa só
- O nome da função dispensa comentário sobre o que ela faz
- Comentário existe para explicar decisão, não mecânica
- Erro tratado explicitamente, nunca silenciado
- Banco de dados só é tocado pelo `repository.py`

---

## 2. Estrutura de Arquivos — Onde Cada Coisa Vive

```
app.py           → rotas HTTP, validação de entrada, resposta ao cliente
repository.py    → todas as queries SQL/ORM (nada de SQL fora daqui)
services.py      → regras de negócio, cálculos, orquestrações
models.py        → definição das tabelas com SQLAlchemy
utils.py         → helpers reutilizáveis sem dependência de banco
config.py        → configurações por ambiente (dev, prod)
```

**Regra dura:** rota não faz query. Query não faz regra de negócio.
Se uma função está fazendo duas dessas coisas, ela precisa ser dividida.

```python
# ERRADO — rota fazendo query direto
@app.route('/api/produtos')
def list_products():
    produtos = db.session.query(Produto).filter_by(
        restaurante_id=session['restaurante_id'],
        ativo=True
    ).all()
    return jsonify([p.to_dict() for p in produtos])

# CORRETO — rota delega pro repository
@app.route('/api/produtos')
@login_required
def list_products():
    try:
        restaurant_id = session.get('restaurante_id')
        products = get_active_products(restaurant_id)
        return jsonify([p.to_dict() for p in products])
    except Exception as e:
        app.logger.error(f"list_products: {e}", exc_info=True)
        return jsonify({'erro': 'Erro ao buscar produtos'}), 500
```

---

## 3. Rotas Flask

### Estrutura padrão de uma rota

```python
@app.route('/api/pedidos/<int:order_id>', methods=['GET'])
@login_required
def get_order(order_id):
    # 1. Pega contexto da sessão
    restaurant_id = session.get('restaurante_id')

    # 2. Valida entrada quando necessário
    if not order_id or order_id < 1:
        return jsonify({'erro': 'ID inválido'}), 400

    # 3. Chama repository/service
    try:
        order = get_order_by_id(order_id, restaurant_id)
        if not order:
            return jsonify({'erro': 'Pedido não encontrado'}), 404
        return jsonify(order.to_dict())
    except Exception as e:
        app.logger.error(f"get_order id={order_id}: {e}", exc_info=True)
        return jsonify({'erro': 'Erro interno'}), 500
```

### Regras de rota

- Sempre usa `session.get('restaurante_id')` — nunca pega do formulário
- Valida entrada antes de tocar no banco
- Retorna JSON com chave `erro` em caso de falha (o frontend espera isso)
- HTTP status codes corretos: 200, 201, 400, 403, 404, 500
- Rota com mais de 25 linhas: mova lógica para `services.py`

### Métodos HTTP corretos

```
GET    → buscar dados (sem efeito colateral)
POST   → criar novo recurso
PUT    → atualizar recurso completo
PATCH  → atualizar campo específico
DELETE → remover recurso
```

---

## 4. Repository — Padrão de Queries

Todo acesso ao banco vive aqui. Nada de query em rota ou service.

### Estrutura padrão de função no repository

```python
# repository.py

def get_active_products(restaurant_id: int) -> list:
    """
    Retorna produtos ativos de um restaurante ordenados por categoria.
    Produtos inativos são ocultados do cardápio mas mantidos no histórico.
    """
    return (
        db.session.query(Produto)
        .filter_by(restaurante_id=restaurant_id, ativo=True)
        .order_by(Produto.categoria_id, Produto.nome)
        .all()
    )


def get_order_by_id(order_id: int, restaurant_id: int):
    """
    Busca pedido garantindo isolamento de tenant.
    Retorna None se não encontrado ou se pertencer a outro restaurante.
    """
    return (
        db.session.query(Pedido)
        .filter_by(id=order_id, restaurante_id=restaurant_id)
        .first()
    )


def create_order(restaurant_id: int, table_id: int, canal: str) -> Pedido:
    """
    Cria pedido e persiste no banco.
    canal: 'mesa' | 'delivery' | 'balcao'
    """
    order = Pedido(
        restaurante_id=restaurant_id,
        mesa_id=table_id,
        canal=canal,
        status='aberto',
    )
    db.session.add(order)
    db.session.commit()
    return order
```

### Regras do repository

- Toda função tem type hints nos parâmetros
- Toda função tem docstring explicando a decisão de negócio relevante
- Commit só acontece aqui, nunca na rota ou no service
- Em caso de erro de banco, deixa a exceção subir — o try/except fica na rota
- Sempre filtra por `restaurante_id` em qualquer query de dados do tenant

### Transações com rollback

```python
def transfer_order_to_table(order_id: int, new_table_id: int, restaurant_id: int):
    """
    Move pedido para outra mesa. Operação atômica — ou tudo funciona ou nada muda.
    """
    try:
        order = get_order_by_id(order_id, restaurant_id)
        if not order:
            raise ValueError(f"Pedido {order_id} não encontrado")

        order.mesa_id = new_table_id
        db.session.commit()
        return order
    except Exception:
        db.session.rollback()
        raise  # deixa a rota tratar e logar
```

---

## 5. Models — Definição das Tabelas

```python
# models.py
from datetime import datetime
from app import db


class Pedido(db.Model):
    __tablename__ = 'pedidos'

    id = db.Column(db.Integer, primary_key=True)
    restaurante_id = db.Column(db.Integer, db.ForeignKey('restaurantes.id'), nullable=False)
    mesa_id = db.Column(db.Integer, db.ForeignKey('mesas.id'), nullable=True)
    canal = db.Column(db.Enum('mesa', 'delivery', 'balcao'), nullable=False, default='mesa')
    status = db.Column(db.Enum('aberto', 'em_preparo', 'pronto', 'entregue', 'cancelado'), default='aberto')
    criado_em = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    atualizado_em = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relacionamentos
    itens = db.relationship('ItemPedido', backref='pedido', lazy='dynamic')

    def to_dict(self) -> dict:
        """Serialização segura — nunca expõe campos internos desnecessários."""
        return {
            'id': self.id,
            'mesa_id': self.mesa_id,
            'canal': self.canal,
            'status': self.status,
            'criado_em': self.criado_em.isoformat(),
        }

    def __repr__(self):
        return f'<Pedido id={self.id} status={self.status}>'
```

### Regras de model

- Sempre tem `restaurante_id` com ForeignKey em entidades do tenant
- Sempre tem `criado_em` com `default=datetime.utcnow`
- `to_dict()` define o que o frontend vê — não exponha campos sensíveis
- Use `db.Enum` para campos com valores fixos (status, canal, tipo)
- `__repr__` útil para debug no terminal

---

## 6. Tratamento de Erros

### Hierarquia de tratamento

```
Rota → captura tudo, loga, retorna JSON de erro pro cliente
Repository → deixa exceção subir (faz rollback se necessário)
Service → pode capturar para adicionar contexto, mas relança
```

### Erros customizados para lógica de negócio

```python
# utils.py — erros de domínio, não de infraestrutura

class OrderNotFoundError(Exception):
    """Pedido não existe ou não pertence ao restaurante."""
    pass

class TableAlreadyOpenError(Exception):
    """Mesa já possui pedido em aberto."""
    pass

class InvalidOrderStatusError(Exception):
    """Transição de status inválida (ex: 'entregue' → 'aberto')."""
    pass
```

```python
# Na rota, trata cada tipo de erro com status HTTP correto
@app.route('/api/mesas/<int:table_id>/abrir', methods=['POST'])
@login_required
def open_table(table_id):
    restaurant_id = session.get('restaurante_id')
    try:
        order = open_table_service(table_id, restaurant_id)
        return jsonify(order.to_dict()), 201
    except TableAlreadyOpenError as e:
        return jsonify({'erro': str(e)}), 409  # Conflict
    except Exception as e:
        app.logger.error(f"open_table table_id={table_id}: {e}", exc_info=True)
        return jsonify({'erro': 'Erro interno'}), 500
```

### O que NUNCA fazer com erros

```python
# NUNCA — silencia o erro, impossível debugar
try:
    do_something()
except:
    pass

# NUNCA — expõe traceback pro cliente
except Exception as e:
    return jsonify({'erro': str(e)}), 500

# NUNCA — loga sem contexto
except Exception as e:
    print(e)
```

---

## 7. Logging

### Padrão de log por nível

```python
# DEBUG — estado interno, só em desenvolvimento
app.logger.debug(f"Calculando frete: origem={origin} destino={dest}")

# INFO — eventos normais de negócio
app.logger.info(f"Pedido criado: id={order.id} restaurante={restaurant_id}")

# WARNING — algo inesperado mas não quebrou
app.logger.warning(f"Produto sem categoria: produto_id={product_id}")

# ERROR — falha que precisa investigação, sempre com exc_info=True
app.logger.error(f"Falha ao abrir mesa id={table_id}: {e}", exc_info=True)
```

### Regras de log

- Sempre inclui o ID do recurso envolvido (`order_id`, `restaurant_id`)
- Nunca loga senha, token, CPF ou dado pessoal
- `exc_info=True` no ERROR para capturar o traceback completo no arquivo de log
- Em produção: `DEBUG=False`, logs vão para arquivo, não para stdout

---

## 8. Configuração por Ambiente

```python
# config.py
import os


class Config:
    SECRET_KEY = os.environ['SECRET_KEY']
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'


class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'sqlite:///dev.db')
    SESSION_COOKIE_SECURE = False


class ProductionConfig(Config):
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = os.environ['DATABASE_URL']
    SESSION_COOKIE_SECURE = True  # só HTTPS
    SQLALCHEMY_POOL_SIZE = 10
    SQLALCHEMY_POOL_RECYCLE = 280  # evita timeout do MySQL após idle
```

```python
# app.py — carrega config pelo ambiente
config_map = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
}
env = os.environ.get('FLASK_ENV', 'development')
app.config.from_object(config_map[env])
```

---

## 9. Boas Práticas Extras

### Decimal no JSON (bug recorrente)

```python
# utils.py
import decimal

def safe_jsonify(data: dict) -> dict:
    """Converte Decimal para float antes de serializar."""
    for key, value in data.items():
        if isinstance(value, decimal.Decimal):
            data[key] = float(value)
    return data
```

### Paginação em listagens grandes

```python
# repository.py — evita trazer 10.000 pedidos de uma vez
def get_orders_paginated(restaurant_id: int, page: int = 1, per_page: int = 20):
    return (
        db.session.query(Pedido)
        .filter_by(restaurante_id=restaurant_id)
        .order_by(Pedido.criado_em.desc())
        .paginate(page=page, per_page=per_page, error_out=False)
    )
```

### Não use `SELECT *` implícito quando só precisa de campos específicos

```python
# Quando só precisa do nome e preço, não carrega a foto (blob pesado)
produtos = (
    db.session.query(Produto.id, Produto.nome, Produto.preco)
    .filter_by(restaurante_id=restaurant_id, ativo=True)
    .all()
)
```

---

## 10. Checklist do Agente

Antes de entregar qualquer código backend, verifique:

- [ ] Rota tem `@login_required`?
- [ ] `restaurante_id` vem da sessão, nunca do formulário/URL?
- [ ] Query está no `repository.py`, não na rota?
- [ ] Toda rota tem try/except com `app.logger.error(..., exc_info=True)`?
- [ ] Erros de negócio usam exceções customizadas?
- [ ] Nenhum `except: pass` ou `except Exception as e: return str(e)`?
- [ ] `to_dict()` não expõe dados sensíveis?
- [ ] Funções têm type hints e docstring quando necessário?
- [ ] Commit só acontece no repository?
- [ ] Decimal convertido antes de `jsonify`?
-
