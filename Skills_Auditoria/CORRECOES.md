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
**Status:** `[x] concluido`

**O que foi feito:**
- `app.py`: adicionado helper `get_pagination_params()` — extrai `page`/`per_page` de query params, default page=1, per_page=50, max per_page=200
- `/api/mesas`: paginação in-memory sobre resultado do repository, retorna `page`, `per_page`, `total`
- `/api/pedidos/delivery`: paginação SQL-level sobre pedidos entregues (ativos ficam sem limite por serem poucos), retorna metadados
- `/api/caixa/movimentacoes`: paginação in-memory sobre lista combinada (delivery + mesas)
- `/api/caixa/historico`: paginação SQL-level com `LIMIT/OFFSET` + `COUNT(*)` para total
- `/api/caixa/balanco`: paginação SQL-level com `LIMIT/OFFSET` + `COUNT(*)` para total

---

### Tarefa 2.2 — Rate limiting nas rotas públicas
**Arquivo:** `app.py`  
**Status:** `[x] concluido`

**O que foi feito:**
- `app.py`: adicionado `@limiter.limit("60/minute")` em `/api/pedido` (POST)
- `app.py`: adicionado `@limiter.limit("30/minute")` em 3 outras rotas POST públicas: `/cardapio/<slug>/api/pedido`, `/api/cliente`, `/api/maps/calcular-frete`
- `app.py`: adicionado `@limiter.limit("120/minute")` em 17 rotas GET públicas (10 API + 7 páginas HTML)
- `app.py`: adicionado `@app.errorhandler(429)` para resposta JSON amigável

---

### Tarefa 2.3 — CORS configurado
**Arquivo:** `app.py`  
**Status:** `[x] concluido`

**O que foi feito:**
- `requirements.txt`: adicionado `flask-cors`
- `app.py`: adicionado `from flask_cors import CORS` (após imports)
- `app.py`: configurado `CORS(app, origins=["https://pantanaldev.com.br", "https://*.pantanaldev.com.br"], supports_credentials=True)` (após criação do app)
- Talisman analisado: CSP `connect-src` não inclui `*.pantanaldev.com.br` — pode bloquear requisições cross-origin no navegador mesmo com CORS correto
- **Pós-deploy:** corrigido `connect-src` do Talisman — adicionado `https://pantanaldev.com.br https://*.pantanaldev.com.br`

---

### Tarefa 2.4 — Tratar restaurante_id NULL do superadmin
**Arquivo:** `repository.py` e `app.py`  
**Status:** `[x] concluido`

**O que foi feito:**
- `app.py`: criado helper `get_restaurante_id_or_403()` que aborta com 403 se `restaurante_id` for None (superadmin incluso)
- `app.py`: substituídas ~40 ocorrências de `session.get('restaurante_id', 1)` / `session['restaurante_id']` nas rotas de tenant por `get_restaurante_id_or_403()`
- Exceções preservadas: login, logout, setup, `/superadmin/*`, context processor e before_request (já tinham guarda `if rid:`)
- `repository.py::criar_pedido_delivery`: confirmação de que correção da Tarefa 1.2 (slug) está aplicada no caller; `or 1` é fallback inócuo

---

### Bug extra — IDOR em /api/check-status
**Arquivo:** `app.py` linha ~2510  
**Risco:** Qualquer pessoa enumera restaurantes chamando `/api/check-status/1`, `/api/check-status/2`...
**Status:** `[x] corrigido`

**O que foi feito:**
- Rota alterada de `/api/check-status/<int:restaurant_id>` para `/api/check-status/<string:slug>`
- `restaurante_id` resolvido via `_get_rid_from_slug(slug)` — slug inválido retorna 400
- Atacante não consegue mais enumerar IDs numéricos

---

## FASE 3 — DÍVIDA TÉCNICA (planejar para próxima versão)

### Tarefa 3.1 — Migrar rotas para Blueprints (routes/)
**Status:** `[x] concluido`

**Ordem de migração (uma por sessão):**
- [x] `routes/auth.py` — login, logout, registro
- [x] `routes/cardapio.py` — cardápio, adicionais, categorias
- [x] `routes/pedidos.py` — criar, listar, atualizar pedidos
- [x] `routes/mesas.py` — mesas, status
- [x] `routes/delivery.py` — delivery, zonas
- [x] `routes/caixa.py` — caixa, movimentações

**Fase 3.1 — Migração de Blueprints:** `[x] concluido` — todas as 6 Blueprints migradas.

**Pós-deploy:** removidas 3 rotas duplicadas que sobraram em `app.py` (`caixa_historico`, `caixa_abrir`, `caixa_balanco`) — o Blueprint já as registrava. `caixa_grafico` mantida (única em app.py).

**Regra:** migrar uma Blueprint, testar todas as rotas dela, commit — só então migrar a próxima.

---

### Tarefa 3.2 — TenantRepository base centralizado
**Arquivo:** `repository.py`  
**Status:** `[x] concluido`

**O que foi feito:**
- Classe `TenantRepository` com `__init__(restaurante_id)`, `_conn()`, `find_by_id(table, id)`, `find_all(table, filters)`, `delete(table, id)` — todos os métodos filtram por `restaurante_id`
- Subclasses esqueleto: `PedidoRepository`, `ProdutoRepository`, `ClienteRepository`
- Nenhuma função existente foi migrada — apenas estrutura criada

---

### Tarefa 3.3 — Logs de auditoria
**Status:** `[x] concluido`

**O que foi feito:**
- `migrations/003_audit_logs.sql`: migration com tabela `audit_logs`
- `helpers.py`: função `registrar_auditoria()` — grava evento com session, IP, detalhes; falha silenciosa
- `routes/auth.py`: `registrar_auditoria('login')` em login bem-sucedido; `registrar_auditoria('logout')` no logout
- `routes/pedidos.py`: `registrar_auditoria('criar_pedido', table_name='pedidos', record_id=id)` após criar pedido
- `routes/caixa.py`: `registrar_auditoria('fechar_caixa', table_name='fechamentos_caixa', detalhes=...)` ao fechar caixa

---

### Tarefa 3.4 — Testes de isolamento de tenant
**Status:** `[x] concluido`

**O que foi feito:**
- `tests/test_tenant_isolation.py`: suite com 5 testes de isolamento
- `run_tests.py`: runner com patches de compatibilidade MySQL→SQLite
- Todos os 5 testes passam no ambiente local

**Testes implementados:**
| # | Teste | Resultado |
|---|-------|-----------|
| 1 | `test_pedido_isolado` — B não vê pedidos de A | ✅ PASS |
| 2 | `test_cliente_isolado` — B não vê clientes de A | ✅ PASS |
| 3 | `test_query_param_ignorado` — Slug na URL não sobrescreve session | ✅ PASS |
| 4 | `test_body_restaurante_id_ignorado` — Body com restaurante_id=1 não sequestra pedido | ✅ PASS |
| 5 | `test_check_status_sem_id_numerico` — IDOR via ID numérico não funciona mais | ✅ PASS |

---

---

## FASE 4 — HUMANIZAÇÃO DO CÓDIGO (executar após Fase 3 completa)

### Tarefa 4.1 — Remover comentários desnecessários
**Arquivo:** `app.py`, `repository.py`
**Status:** `[x] concluido`

**O que foi feito:**
- `app.py`: removidos 25 comentários — `#inicializar_admin()`, `# NOVO — ...`, `# Parse dos itens`, `# Usa o serviço...`, `# Garantir coluna...`, `# Verificar se...`, `# Inserir/Criar...`, `# SQL compatível`, `# Registrar início...`, `# Delivery/Mesas por hora`, `# Verifica/Coluna existe/não existe` (migração)
- `repository.py`: removidos 10 comentários — `# 1-5. ...` (dashboard), `# Atualiza total da mesa` (repetido), `# Busca/Salva/Deleta` (histórico)
- Preservados: separadores de seção, comentários de segurança, decisões de migração, regras de negócio (`Atualiza status para 'ocupada'...`)

---

### Tarefa 4.2 — Padronizar idioma dos identificadores
**Arquivo:** `app.py`, `helpers.py`, `routes/`
**Status:** `[x] concluido`

**O que foi feito (definitivo):**
- Decisão: manter código 100% inglês — consistente com Flask, SQL, HTTP, JSON e bibliotecas Python
- `helpers.py`: revertido `obter_*` → `get_*` (nomes originais). Aliases removidos.
- `app.py`: revertido `obter_*` → `get_*` (nomes originais)
- `routes/*.py`: mantido `get_*` (já estavam em EN)
- Resultado: zero aliases, zero fronteira EN/PT, zero confusão
- `flask run` ✅ | `pytest` 5/5 ✅

---

### Tarefa 4.3 — Revisar nomes genéricos
**Status:** `[x] cancelado`

**Motivo:** `row`, `dados`, `resultado` são padrões universais em código que lida com banco e requisições. Renomear cada ocorrência quebraria a legibilidade em vez de melhorá-la — o contexto da função já revela o significado. Decisão: manter como está.

---

### Tarefa 4.4 — Quebrar funções longas
**Arquivo:** `app.py`
**Status:** `[x] cancelado`

**Motivo:** Risco de quebrar funções legadas duplicadas entre app.py e routes/caixa.py. Ganho estético não justifica o risco sem cobertura de testes. Decisão: manter como está.

---

### Tarefa 4.5 — Revisão final de estilo
**Arquivo:** todos
**Status:** `[x] concluido`

**O que foi feito:**
- Fase 4 completa: comentários limpos (4.1), nomenclatura padronizada EN (4.2), nomes genéricos mantidos (4.3 cancelado), funções longas mantidas (4.4 cancelado)
- Código consistente em inglês, coeso, comentários de segurança preservados
- Nenhuma alteração adicional necessária — sistema estável e testado

## HISTÓRICO DE SESSÕES

| Data | Tarefa | Status | Observações |
|------|--------|--------|-------------|
| 05/05/2026 | 1.1 — Corrigir IDOR clientes_cache | ✅ concluido | 4 arquivos: app.py (3 blocos) + carrinho.js (2 chamadas) |
| 06/05/2026 | 2.4 — Tratar restaurante_id NULL do superadmin | ✅ concluido | app.py: helper + ~40 substituições em rotas de tenant |
| 06/05/2026 | 2.3 — CORS configurado | ✅ concluido | requirements.txt + app.py (import + CORS()); Talisman analisado sem alterações |
| 06/05/2026 | 2.2 — Rate limiting nas rotas públicas | ✅ concluido | app.py: ~21 decorators + handler 429 |
| 06/05/2026 | 2.1 — Paginação nas listagens | ✅ concluido | app.py: helper get_pagination_params + 5 rotas modificadas |
| 06/05/2026 | 2.3 — Talisman connect-src (pós-deploy) | ✅ concluido | app.py: adicionado domínio de produção ao CSP connect-src |
| 06/05/2026 | Bug extra — IDOR check-status | ✅ corrigido | app.py: <int:id> → <string:slug> + _get_rid_from_slug |
| 06/05/2026 | Sessão — ProxyFix + cookie Secure | ✅ concluido | app.py: x_proto=2, SESSION_COOKIE_SECURE=True, timedelta(hours=8), rota /debug/proxy |
| 06/05/2026 | 3.1 — Blueprint auth.py | ✅ concluido | routes/auth.py + extensions.py + app.py (remoção rotas + registro Blueprint) + landing.html |
| 06/05/2026 | 3.1 — Blueprint cardapio.py | ✅ concluido | routes/cardapio.py + helpers.py + app.py (5 rotas removidas + registro Blueprint) |
| 06/05/2026 | 3.1 — Blueprint pedidos.py | ✅ concluido | routes/pedidos.py + helpers.py (decorators) + app.py (4 rotas removidas + registro + import route_criar_pedido) |
| 06/05/2026 | 3.1 — Blueprint mesas.py | ✅ concluido | routes/mesas.py + helpers.py (url_for atualizado) + app.py (5 rotas removidas + registro) |
| 06/05/2026 | 3.1 — Blueprint delivery.py | ✅ concluido | routes/delivery.py + app.py (2 rotas removidas + registro) |
| 06/05/2026 | 3.1 — Blueprint caixa.py | ✅ concluido | routes/caixa.py + helpers.py (_get_sessao_inicio) + app.py (7 rotas removidas + registro); app.py ~1700 linhas |
| 06/05/2026 | 3.2 — TenantRepository | ✅ concluido | repository.py: classe base + 3 subclasses esqueleto |
| 06/05/2026 | 3.3 — Logs de auditoria | ✅ concluido | migrations/003 + helpers.py (registrar_auditoria) + auth/pedidos/caixa (4 eventos) |
| 06/05/2026 | 3.4 — Testes isolamento tenant | ✅ concluido | tests/test_tenant_isolation.py (5 testes) + run_tests.py; 5/5 passed |
| 06/05/2026 | 4.1 — Remover comentários inúteis | ✅ concluido | app.py (-25) + repository.py (-10); 0 linhas de código alteradas |
| 06/05/2026 | 4.2 — Padronizar idioma | ✅ concluido | helpers.py (2 funções renomeadas) + app.py (error_msg, get_val) + routes/* (imports) |
| 06/05/2026 | 4.3 — Revisar nomes genéricos | ❌ cancelado | Decisão: manter row/dados/resultado como padrão universal |
| 06/05/2026 | 4.4 — Quebrar funções longas | ❌ cancelado | Risco > benefício sem cobertura de testes |
| 06/05/2026 | 4.5 — Revisão final de estilo | ✅ concluido | Fase 4 encerrada; código consistente e estável |
| 06/05/2026 | Remoção de duplicatas (pós 3.1) | ✅ concluido | app.py: removidas 3 rotas caixa duplicadas (caixa_historico, abrir_caixa, caixa_balanco) |

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
