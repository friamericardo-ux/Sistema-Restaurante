# SKILL: SaaS Multi-Tenant Seguro — FastAPI + MySQL
> Boas práticas para sistemas SaaS com isolamento por restaurante (tenant),
> focado em segurança, escalabilidade e responsividade. Versão 1.0

---

## 1. MODELO DE ISOLAMENTO MULTI-TENANT

### Estratégia recomendada: Row-Level Isolation (isolamento por linha)
Cada tabela possui uma coluna `restaurant_id` (tenant_id) que identifica o dono dos dados.

```sql
-- Toda tabela de negócio DEVE ter restaurant_id
CREATE TABLE orders (
    id           BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    restaurant_id BIGINT UNSIGNED NOT NULL,  -- ← OBRIGATÓRIO
    table_number INT,
    status       ENUM('open','closed','cancelled') DEFAULT 'open',
    created_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_restaurant_id (restaurant_id),   -- ← ÍNDICE OBRIGATÓRIO
    FOREIGN KEY (restaurant_id) REFERENCES restaurants(id) ON DELETE CASCADE
);
```

### Tabelas que DEVEM ter restaurant_id
- orders, order_items
- tables (mesas)
- products, categories
- customers
- delivery_zones
- employees / staff
- sessions / tokens de funcionários

### Tabelas GLOBAIS (sem restaurant_id)
- restaurants (a própria tabela de tenants)
- plans / subscriptions
- system_logs

---

## 2. CAMADA DE SEGURANÇA NO FASTAPI

### 2.1 Middleware de Tenant — extrair restaurant_id do JWT

```python
# app/core/security.py
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt

SECRET_KEY = "sua-chave-secreta-forte"  # use variável de ambiente
ALGORITHM = "HS256"

bearer_scheme = HTTPBearer()

def get_current_restaurant(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)
) -> int:
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        restaurant_id: int = payload.get("restaurant_id")
        if restaurant_id is None:
            raise HTTPException(status_code=401, detail="Token inválido")
        return restaurant_id
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expirado")
    except jwt.JWTError:
        raise HTTPException(status_code=401, detail="Token inválido")
```

### 2.2 Uso nas rotas — restaurant_id sempre injetado

```python
# app/routes/orders.py
from fastapi import APIRouter, Depends
from app.core.security import get_current_restaurant
from app.db import get_db

router = APIRouter()

@router.get("/orders")
def list_orders(
    restaurant_id: int = Depends(get_current_restaurant),
    db = Depends(get_db)
):
    # NUNCA aceite restaurant_id do body/query — sempre do token!
    return db.execute(
        "SELECT * FROM orders WHERE restaurant_id = %s", (restaurant_id,)
    ).fetchall()

@router.get("/orders/{order_id}")
def get_order(
    order_id: int,
    restaurant_id: int = Depends(get_current_restaurant),
    db = Depends(get_db)
):
    order = db.execute(
        "SELECT * FROM orders WHERE id = %s AND restaurant_id = %s",
        (order_id, restaurant_id)  # ← SEMPRE filtrar pelos dois
    ).fetchone()
    if not order:
        raise HTTPException(status_code=404, detail="Pedido não encontrado")
    return order
```

---

## 3. FALHAS CRÍTICAS A EVITAR (IDOR — Insecure Direct Object Reference)

### ❌ ERRADO — vulnerável
```python
@router.get("/orders/{order_id}")
def get_order(order_id: int, db = Depends(get_db)):
    # Restaurante A pode acessar pedidos do Restaurante B!
    return db.execute("SELECT * FROM orders WHERE id = %s", (order_id,)).fetchone()
```

### ✅ CORRETO — seguro
```python
@router.get("/orders/{order_id}")
def get_order(
    order_id: int,
    restaurant_id: int = Depends(get_current_restaurant),
    db = Depends(get_db)
):
    order = db.execute(
        "SELECT * FROM orders WHERE id = %s AND restaurant_id = %s",
        (order_id, restaurant_id)
    ).fetchone()
    if not order:
        raise HTTPException(status_code=404)
    return order
```

### Checklist de IDOR — revisar em TODA rota:
- [ ] Toda query de SELECT filtra `restaurant_id`?
- [ ] Todo UPDATE filtra `restaurant_id`?
- [ ] Todo DELETE filtra `restaurant_id`?
- [ ] Nenhuma rota aceita `restaurant_id` do usuário (body/query/param)?

---

## 4. CAMADA DE REPOSITÓRIO (Repository Pattern)

Centraliza o filtro de tenant para evitar esquecer em queries:

```python
# app/repositories/base.py
class TenantRepository:
    def __init__(self, db, restaurant_id: int):
        self.db = db
        self.restaurant_id = restaurant_id
        self.table = ""  # sobrescrever na subclasse

    def find_by_id(self, record_id: int):
        row = self.db.execute(
            f"SELECT * FROM {self.table} WHERE id = %s AND restaurant_id = %s",
            (record_id, self.restaurant_id)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404)
        return row

    def find_all(self, limit=50, offset=0):
        return self.db.execute(
            f"SELECT * FROM {self.table} WHERE restaurant_id = %s LIMIT %s OFFSET %s",
            (self.restaurant_id, limit, offset)
        ).fetchall()

    def delete(self, record_id: int):
        affected = self.db.execute(
            f"DELETE FROM {self.table} WHERE id = %s AND restaurant_id = %s",
            (record_id, self.restaurant_id)
        ).rowcount
        if affected == 0:
            raise HTTPException(status_code=404)

# app/repositories/orders.py
class OrderRepository(TenantRepository):
    table = "orders"
```

---

## 5. ÍNDICES MySQL — PERFORMANCE MULTI-TENANT

```sql
-- Índices compostos para queries frequentes
ALTER TABLE orders      ADD INDEX idx_tenant_status  (restaurant_id, status);
ALTER TABLE orders      ADD INDEX idx_tenant_created (restaurant_id, created_at);
ALTER TABLE order_items ADD INDEX idx_tenant_order   (restaurant_id, order_id);
ALTER TABLE products    ADD INDEX idx_tenant_active  (restaurant_id, active);
ALTER TABLE tables      ADD INDEX idx_tenant_status  (restaurant_id, status);

-- Nunca fazer full table scan em produção
-- EXPLAIN SELECT * FROM orders WHERE restaurant_id = 1; -- checar se usa índice
```

---

## 6. VARIÁVEIS DE AMBIENTE — NUNCA hardcode

```bash
# .env (não commitar no git!)
DATABASE_URL=mysql+pymysql://user:password@localhost:3306/comanda_db
SECRET_KEY=chave-jwt-minimo-32-chars-aleatoria
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=480
ENVIRONMENT=production
```

```python
# app/core/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 480
    environment: str = "development"

    class Config:
        env_file = ".env"

settings = Settings()
```

---

## 7. RATE LIMITING — PROTEÇÃO CONTRA ABUSO

```python
# Instalar: pip install slowapi
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@router.post("/orders")
@limiter.limit("60/minute")  # máx 60 pedidos por minuto por IP
def create_order(request: Request, ...):
    ...
```

---

## 8. LOGS DE AUDITORIA

```sql
CREATE TABLE audit_logs (
    id            BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    restaurant_id BIGINT UNSIGNED NOT NULL,
    user_id       BIGINT UNSIGNED,
    action        VARCHAR(50) NOT NULL,  -- 'CREATE_ORDER', 'DELETE_PRODUCT'
    table_name    VARCHAR(50),
    record_id     BIGINT UNSIGNED,
    ip_address    VARCHAR(45),
    created_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_tenant_action (restaurant_id, action),
    INDEX idx_tenant_date   (restaurant_id, created_at)
);
```

---

## 9. CHECKLIST DE AUDITORIA DE SEGURANÇA

### Isolamento de Tenant
- [ ] Toda tabela de negócio tem `restaurant_id`
- [ ] Todo SELECT filtra `restaurant_id`
- [ ] Todo UPDATE filtra `restaurant_id`
- [ ] Todo DELETE filtra `restaurant_id`
- [ ] Nenhuma rota expõe dados de outro tenant

### Autenticação
- [ ] JWT com expiração configurada
- [ ] `restaurant_id` extraído do token, nunca do request
- [ ] Senhas com bcrypt (custo >= 12)
- [ ] Tokens de refresh com rotação

### Banco de Dados
- [ ] Índices em todas as colunas `restaurant_id`
- [ ] Índices compostos nas queries mais frequentes
- [ ] Queries usam parâmetros bindados (sem SQL injection)
- [ ] Usuário do banco com permissões mínimas

### Infraestrutura
- [ ] Variáveis sensíveis em `.env` (não no código)
- [ ] `.env` no `.gitignore`
- [ ] HTTPS obrigatório em produção
- [ ] CORS configurado apenas para domínios autorizados
- [ ] Rate limiting nas rotas públicas

### Dados
- [ ] Paginação em todas as listagens (sem retornar tudo)
- [ ] Validação de input com Pydantic
- [ ] Logs de auditoria para ações críticas

---

## 10. ESTRUTURA DE PASTAS RECOMENDADA

```
comanda/
├── app/
│   ├── core/
│   │   ├── config.py        # variáveis de ambiente
│   │   ├── security.py      # JWT, get_current_restaurant
│   │   └── database.py      # conexão MySQL
│   ├── models/
│   │   ├── restaurant.py
│   │   ├── order.py
│   │   └── product.py
│   ├── repositories/
│   │   ├── base.py          # TenantRepository
│   │   ├── orders.py
│   │   └── products.py
│   ├── routes/
│   │   ├── auth.py
│   │   ├── orders.py
│   │   ├── products.py
│   │   └── delivery.py
│   ├── schemas/             # Pydantic models
│   └── main.py
├── tests/
│   ├── test_tenant_isolation.py  # ← CRÍTICO testar isso
│   └── test_auth.py
├── .env                     # não commitar!
├── .env.example             # commitar (sem valores reais)
├── .gitignore
└── requirements.txt
```

---

## 11. TESTE DE ISOLAMENTO DE TENANT (obrigatório)

```python
# tests/test_tenant_isolation.py
def test_restaurante_nao_acessa_pedido_de_outro(client, token_restaurante_1, token_restaurante_2):
    # Criar pedido no restaurante 1
    r = client.post("/orders", json={...}, headers={"Authorization": f"Bearer {token_restaurante_1}"})
    order_id = r.json()["id"]

    # Restaurante 2 NÃO deve conseguir acessar
    r2 = client.get(f"/orders/{order_id}", headers={"Authorization": f"Bearer {token_restaurante_2}"})
    assert r2.status_code == 404  # ← deve retornar 404, não 200!
```

---

*Skill criada para: Comanda Digital — FastAPI + MySQL*
*Padrão: SaaS Multi-Tenant Row-Level Isolation*
*Versão: 1.0 | Atualizar conforme o sistema evoluir*
