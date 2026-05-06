# PLANO DE IMPLEMENTAÇÃO — Módulo Robô / WhatsApp
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
7. **Idioma do código: inglês** — variáveis, funções, rotas, comentários técnicos em inglês.
8. **Sem default `or 1`** — nunca usar fallback para restaurante_id fixo.
9. **Sem comentários desnecessários** — apenas comentários de segurança ou decisão de negócio.
10. **Novas rotas seguem o padrão Blueprint** — criar em `routes/whatsapp.py`, nunca em `app.py`.

---

## CONTEXTO DO SISTEMA ATUAL

### Stack do Comanda Digital
- **Backend:** Flask/Python, multi-tenant, Blueprints em `routes/`
- **Banco:** MySQL via XAMPP (local) / Docker (produção)
- **Hospedagem:** Coolify no servidor alemão
- **Domínio:** pantanaldev.com.br

### Stack do Robô (já funcionando)
- **Evolution API v2.3.7** — gerencia instância WhatsApp
- **n8n** — orquestra o workflow
- **Groq (Llama)** — modelo de IA que responde
- **Instância ativa:** `pantanal-burger` (número da Tais)
- **URL Evolution:** https://evolution.pantanaldev.com.br
- **URL n8n webhook:** https://n8n.pantanaldev.com.br/webhook/comanda-digital

### O que o workflow n8n faz hoje
```
Webhook → Code JS (filtro) → AI Agent (Groq) → HTTP GET cardápio → HTTP POST resposta
```

---

## FASE 1 — INTERFACE NO PAINEL (prioridade)

### Tarefa 1.1 — Blueprint whatsapp.py
**Arquivo:** `routes/whatsapp.py` (novo)
**Status:** `[x] concluido`

**O que fazer:**
- Criar Blueprint `whatsapp_bp` com prefix `/whatsapp`
- Rota `GET /whatsapp/` — página principal do módulo (renderiza `whatsapp/index.html`)
- Rota `GET /whatsapp/status` — retorna JSON com status da instância via Evolution API
- Rota `GET /whatsapp/qrcode` — retorna QR Code da instância via Evolution API
- Rota `POST /whatsapp/toggle` — liga/desliga webhook no n8n (ativa/desativa robô)
- Registrar Blueprint em `app.py` com `login_required`
- **Nunca** expor API key da Evolution no frontend — sempre passar pelo backend

**Critério de conclusão:**
- Blueprint registrado sem erros no `flask run`
- Rotas retornam 200 (status) e 401 (sem login)

---

### Tarefa 1.2 — Template whatsapp/index.html
**Arquivo:** `templates/whatsapp/index.html` (novo)
**Status:** `[x] concluido` — iniciar só após 1.1 aprovada

**O que fazer:**
- Estender `base.html` existente
- Card de status: verde "Conectado" / vermelho "Desconectado"
- QR Code renderizado como `<img>` dentro da página (sem abrir nova aba)
- Toggle liga/desliga robô com feedback visual
- Botão "Abrir WhatsApp Web" — abre `https://web.whatsapp.com` em nova aba (comportamento esperado e aceitável)
- Polling automático a cada 10 segundos para atualizar status
- **Sem iframes externos** — QR Code vem do backend como base64

**Critério de conclusão:**
- Página carrega dentro do painel sem erros de console
- QR Code aparece quando instância está desconectada
- Status atualiza automaticamente

---

### Tarefa 1.3 — Ícone no menu lateral
**Arquivo:** `templates/admin_layout.html` (editar)
**Status:** `[x] concluido` — iniciar só após 1.2 aprovada

**O que fazer:**
- Adicionar item no menu lateral: ícone WhatsApp + texto "Robô"
- Link aponta para `url_for('whatsapp_bp.index')`
- Visível apenas para usuários autenticados (já garantido pelo Blueprint)
- Seguir estilo visual dos outros ícones do menu — não inventar novo padrão

**Critério de conclusão:**
- Ícone aparece no menu lateral após login
- Clique navega para a página do módulo

---

## FASE 2 — CONFIGURAÇÃO DO ROBÔ (próxima versão)

### Tarefa 2.1 — Salvar configurações do robô por restaurante
**Arquivo:** `routes/whatsapp.py`, `repository.py`, migration nova
**Status:** `[ ] pendente` — iniciar só após Fase 1 completa

**O que fazer:**
- Migration `004_whatsapp_config.sql`: tabela `whatsapp_config` com `restaurante_id`, `instance_name`, `webhook_url`, `enabled`, `created_at`
- Rota `GET /whatsapp/config` — retorna config atual do restaurante
- Rota `POST /whatsapp/config` — salva config (instance_name, webhook_url)
- Repository: `WhatsappRepository` extendendo `TenantRepository`
- **Nunca** salvar API key no banco — usar variável de ambiente

**Critério de conclusão:**
- Cada restaurante tem sua própria instância configurada
- Restaurante A não vê config do Restaurante B

---

### Tarefa 2.2 — Criar nova instância pela interface
**Arquivo:** `routes/whatsapp.py`
**Status:** `[ ] pendente` — iniciar só após 2.1 aprovada

**O que fazer:**
- Rota `POST /whatsapp/instance/create` — cria instância na Evolution API com nome gerado pelo slug do restaurante
- Nome da instância: `{slug}-bot` (ex: `pantanal-burger-bot`)
- Após criação, salva na tabela `whatsapp_config`
- Retorna QR Code imediatamente para escanear

**Critério de conclusão:**
- Restaurante cria instância própria sem acessar Evolution API diretamente
- QR Code aparece na tela para escanear

---

## FASE 3 — ROBUSTEZ (dívida técnica)

### Tarefa 3.1 — Trocar Groq gratuito por modelo com mais cota
**Arquivo:** n8n workflow (não mexe em código Flask)
**Status:** `[ ] pendente`

**Opções a avaliar (antes de implementar):**
- Groq pago (mais barato, mesmo stack)
- OpenRouter com modelo gratuito de maior cota
- Ollama local no servidor (zero custo, latência maior)

**Critério de decisão:** custo por mensagem vs latência aceitável para restaurante

---

### Tarefa 3.2 — Filtro anti-spam no workflow
**Arquivo:** n8n — Code JS (já existente)
**Status:** `[ ] pendente`

**O que fazer:**
- Ignorar mensagens de grupos (`remoteJid` contém `@g.us`)
- Ignorar mensagens de broadcast (`remoteJid` contém `broadcast`)
- Ignorar mensagens de status (`remoteJid` contém `status@broadcast`)
- Rate limit por número: máximo 10 mensagens por minuto por cliente
- Log de mensagens ignoradas para debug

---

## PROMPT PADRÃO PARA INICIAR CADA SESSÃO

Cole isso no início de cada conversa com a IA:

```
Leia o arquivo ROBO.md antes de qualquer ação.
Execute apenas a próxima tarefa com status [ ] pendente.
Mostre o diff (antes/depois) de cada alteração.
Não modifique arquivos fora do escopo da tarefa.
Código em inglês — variáveis, funções, rotas.
Seguir padrão Blueprint de routes/ existente.
Ao concluir, marque a tarefa como [x] e aguarde minha aprovação.
```

---

## HISTÓRICO DE SESSÕES

| Data | Tarefa | Status | Observações |
|------|--------|--------|-------------|
| 06/05/2026 | Diagnóstico filtro Code JS | ✅ concluido | Bug: `json.data.key` → `json.body.data.key`; robô voltou a responder |