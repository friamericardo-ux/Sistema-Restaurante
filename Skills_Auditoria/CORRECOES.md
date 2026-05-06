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

---

## FASE 4 — HUMANIZAÇÃO DO CÓDIGO (executar após Fase 3 completa)

### Tarefa 4.1 — Remover comentários desnecessários
**Arquivo:** `app.py`, `repository.py`
**Status:** `[ ] pendente`

**O que fazer:**
- Remover comentários que explicam o óbvio (ex: `# abre conexão`, `# retorna resultado`)
- Manter apenas comentários que explicam o **porquê** de uma decisão não óbvia
- Preservar comentários de segurança (ex: `# slug inválido retorna 400 — não expõe ID`)

---

### Tarefa 4.2 — Padronizar idioma dos identificadores
**Arquivo:** `app.py`, `repository.py`, `security.py`
**Status:** `[ ] pendente`

**O que fazer:**
- Padronizar variáveis, funções e comentários em português
- Eliminar mistura inglês/português no mesmo bloco
- Manter nomes de bibliotecas e padrões Flask como estão (são convenções)

---

### Tarefa 4.3 — Revisar nomes genéricos
**Arquivo:** `app.py`, `repository.py`
**Status:** `[ ] pendente`

**O que fazer:**
- Renomear variáveis genéricas: `dados`, `resultado`, `resposta`, `row`, `r`
- Usar nomes expressivos que revelam a intenção: `pedido_novo`, `config_restaurante`, `linha_caixa`
- Não renomear parâmetros de rotas Flask ou colunas do banco

---

### Tarefa 4.4 — Quebrar funções longas
**Arquivo:** `app.py`
**Status:** `[ ] pendente`

**O que fazer:**
- Identificar funções com mais de 40 linhas
- Extrair blocos com responsabilidade própria em funções auxiliares com nomes expressivos
- Não alterar lógica — apenas reorganizar
- Mostrar diff antes de qualquer extração

---

### Tarefa 4.5 — Revisão final de estilo
**Arquivo:** todos
**Status:** `[ ] pendente`

**O que fazer:**
- Verificar consistência geral após 4.1 a 4.4
- Garantir que nenhuma função faz mais de uma coisa
- Confirmar que o código lido em voz alta faz sentido em português

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
