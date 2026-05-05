# PLANO DE CORREÇÕES — Comanda Digital
> Leia este arquivo COMPLETO antes de qualquer modificação.
> Siga a ordem. Uma tarefa por sessão. Não pule etapas.

---

## REGRAS PARA A IA (ler sempre)

1. **Uma tarefa por sessão** — implemente, teste, aguarde aprovação antes de avançar.
2. **Nunca altere arquivos fora do escopo da tarefa atual.**
3. **Nunca apague código existente sem mostrar o diff antes.**
4. **Sempre mostre o antes e depois** de cada trecho alterado.
5. **Se encontrar um problema não previsto**, pare e informe — não improvise.
6. **Ao concluir cada tarefa**, atualize o status de `[ ]` para `[x]` neste arquivo.

---

## FASE 1 — CRÍTICO (executar antes de qualquer deploy)

### Tarefa 1.1 — Corrigir IDOR em clientes_cache
**Arquivo:** `app.py` linhas 2433–2474  
**Risco:** Restaurante A lê e grava dados de clientes do Restaurante B  
**Status:** `[x] concluido`

**O que foi feito:**
- `_get_rid_from_slug(slug)`: helper que resolve slug → restaurante_id no banco (valida slug ativo)
- `get_cliente()`: aceita `?slug=` (query param), resolve via helper, filtra `AND restaurante_id = ?`
- `salvar_cliente()`: aceita `slug` no body JSON (nunca restaurante_id), resolve via helper
- `_garantir_clientes_cache()`: coluna `restaurante_id` + chave composta `(telefone, restaurante_id)`
- `carrinho.js`: envia `slug` (tirado do hidden input #restauranteSlug) em vez de ID numerico
- `cardapio_cliente.html` + `carrinho_cliente.html`: adicionado hidden `#restauranteSlug`
- Atacante nao consegue injetar restaurante_id — slug invalido retorna 400

**Critério de conclusão:**
- Restaurante B não consegue ver clientes cadastrados pelo Restaurante A
- Teste manual: criar cliente no restaurante 1, logar como restaurante 2, confirmar que não aparece

**Rollback:** revert no git antes de avançar para 1.2

---

### Tarefa 1.2 — Remover restaurante_id do body JSON no /api/pedido
**Arquivo:** `app.py` linha 858  
**Risco:** Atacante injeta qualquer ID e cria pedido em outro restaurante  
**Status:** `[x] concluido` — iniciar só após 1.1 concluída e aprovada

**O que foi feito:**
- `app.py`: removido `restaurante_id = int(dados.get("restaurante_id") or 1)`, substituído por slug lookup via `_get_rid_from_slug(slug)`, resolve e injeta `dados['restaurante_id']` antes de passar ao repository
- `carrinho.js`: corpo do POST agora envia `slug` (tirado do hidden #restauranteSlug) em vez de `restaurante_id`
- `cardapio.js`: `finalizarPedido()` agora envia `slug: SLUG || ''` em vez de `restaurante_id: rid`
- Slug inválido/ausente retorna 400; atacante não consegue injetar restaurante_id

**Nota:** Rota legada `/cardapio` (sem slug) não consegue criar pedido via `/api/pedido` com slug vazio — retorna 400. Isso é intencional: força migração para rotas com slug.

**Rollback:** revert no git antes de avançar para 1.3

---

### Tarefa 1.3 — Remover restaurante_id dos query params públicos
**Arquivos:** `app.py` linhas 822, 843, 1095  
**Rotas:** `/api/cardapio`, `/api/adicionais`, `/api/configuracoes`  
**Risco:** Qualquer pessoa troca o param e vê dados de outro restaurante  
**Status:** `[x] concluido` — iniciar só após 1.2 concluída e aprovada

**O que foi feito:**
- `/api/cardapio`, `/api/adicionais`, `/api/configuracoes`: trocado `request.args.get('restaurante_id', 1)` por slug lookup com fallback para session
- Prioridade: `?slug=` (query param) → resolve via `_get_rid_from_slug(slug)` → se ausente, tenta `session['restaurante_id']` → se ambos ausentes, retorna 400
- `cardapio.js`: `/api/cardapio` e `/api/adicionais` agora enviam `?slug=${SLUG}` em vez de `?restaurante_id=${RID}`
- `carrinho.js`: `/api/configuracoes` agora envia `?slug=` em vez de `?restaurante_id=`
- Páginas autenticadas (atendente, mesas) continuam funcionando via session fallback (não precisam de slug)
- Default `or 1` removido de todas as 3 rotas

**Critério de conclusão:**
- Trocar o query param manualmente não muda o restaurante retornado
- Rotas públicas funcionam via slug sem expor ID numérico
- Rotas autenticadas funcionam via session

**Rollback:** revert no git antes de avançar para Fase 2

---

## FASE 2 — IMPORTANTE (executar após Fase 1 completa)

### Tarefa 2.1 — Adicionar paginação nas listagens
**Arquivos:** rotas de listagem em `app.py`  
**Rotas afetadas:** `/api/pedidos/delivery`, `/api/mesas`, `/api/caixa/movimentacoes` (e outras sem LIMIT)  
**Status:** `[ ] pendente`

**O que fazer:**
- Adicionar `?page=1&per_page=50` como query params opcionais
- Aplicar `LIMIT ? OFFSET ?` em todas as queries de listagem
- Retornar no JSON: `{ "data": [...], "page": 1, "per_page": 50, "total": 200 }`
- Default: `per_page=50`, máximo permitido: `per_page=200`

---

### Tarefa 2.2 — Rate limiting nas rotas públicas
**Arquivo:** `app.py`  
**Status:** `[ ] pendente`

**O que fazer:**
- Aplicar `@limiter.limit("60/minute")` em `/api/pedido` (POST)
- Aplicar `@limiter.limit("120/minute")` em `/api/cardapio` (GET)
- Aplicar `@limiter.limit("30/minute")` em qualquer rota de criação pública

---

### Tarefa 2.3 — CORS configurado
**Arquivo:** `app.py`  
**Status:** `[ ] pendente`

**O que fazer:**
- Instalar `flask-cors` se não instalado
- Configurar `CORS(app, origins=["https://seudominio.com.br"])` — não usar `*`
- Listar explicitamente os domínios dos restaurantes autorizados ou usar wildcard de subdomínio controlado

---

### Tarefa 2.4 — Tratar restaurante_id NULL do superadmin
**Arquivo:** `repository.py` e `app.py`  
**Status:** `[ ] pendente`

**O que fazer:**
- Mapear todas as queries que filtram por `restaurante_id`
- Adicionar verificação: se `restaurante_id is None` e usuário é superadmin, permitir (sem filtro); caso contrário, retornar 403
- Nunca deixar query sem filtro para usuário comum com `restaurante_id = None`

---

## FASE 3 — DÍVIDA TÉCNICA (planejar para próxima versão)

### Tarefa 3.1 — Migrar rotas para Blueprints (routes/)
**Status:** `[ ] pendente`

**Ordem de migração (uma por sessão):**
- [ ] `routes/auth.py` — login, logout, registro
- [ ] `routes/cardapio.py` — cardápio, adicionais, categorias
- [ ] `routes/pedidos.py` — criar, listar, atualizar pedidos
- [ ] `routes/mesas.py` — mesas, status
- [ ] `routes/delivery.py` — delivery, zonas
- [ ] `routes/caixa.py` — caixa, movimentações

**Regra:** migrar uma Blueprint, testar todas as rotas dela, commit — só então migrar a próxima.

---

### Tarefa 3.2 — TenantRepository base centralizado
**Arquivo:** `repository.py`  
**Status:** `[ ] pendente`

**O que fazer:**
- Criar classe `TenantRepository` com `find_by_id`, `find_all`, `delete` que injetam `restaurante_id` automaticamente
- Subclasses: `PedidoRepository`, `ProdutoRepository`, `ClienteRepository`

---

### Tarefa 3.3 — Logs de auditoria
**Status:** `[ ] pendente`

**O que fazer:**
- Criar tabela `audit_logs` com: `restaurante_id`, `user_id`, `action`, `table_name`, `record_id`, `ip_address`, `created_at`
- Registrar: criar pedido, excluir produto, fechar caixa, login/logout

---

### Tarefa 3.4 — Testes de isolamento de tenant
**Status:** `[ ] pendente`

**Testes obrigatórios:**
- Restaurante B não acessa pedido do Restaurante A
- Restaurante B não acessa clientes do Restaurante A
- Query param trocado não muda o tenant retornado
- Body com restaurante_id diferente é ignorado

---

## HISTÓRICO DE SESSÕES

| Data | Tarefa | Status | Observações |
|------|--------|--------|-------------|
| 05/05/2026 | 1.1 — Corrigir IDOR clientes_cache | ✅ concluido | 4 arquivos: app.py (3 blocos) + carrinho.js (2 chamadas) |

---

## PROMPT PADRÃO PARA INICIAR CADA SESSÃO

Cole isso no início de cada conversa com a IA:

```
Leia o arquivo CORRECOES.md antes de qualquer ação.
Execute apenas a próxima tarefa com status [ ] pendente.
Mostre o diff (antes/depois) de cada alteração.
Não modifique arquivos fora do escopo da tarefa.
Ao concluir, marque a tarefa como [x] e aguarde minha aprovação.
```
