# Arquiteto SaaS Fullstack (Python/Flask)

**Descrição:** Use SEMPRE que o usuário solicitar desenvolvimento, refatoração ou manutenção no SaaS. Esta skill orquestra boas práticas, segurança crítica (OWASP 2026) e eficiência de tokens através de revelação progressiva.

## Princípios de Operação (Token Saving)
1. **Contexto sob demanda:** Não carregue lógica complexa no chat. Se a tarefa for específica, consulte o agente em `agents/`.
2. **Código Enxuto:** Remova verbosidade. Se uma lógica pode ser feita nativamente (ex: CSS nativo em vez de biblioteca JS), faça [5].

## Fluxo de Trabalho
- **Backend/DB:** Para rotas Flask e migrações, leia `agents/flask-db.md`.
- **Segurança:** Todo código deve ser validado contra `agents/security.md`.
- **Frontend:** Para interfaces React/Tailwind, leia `agents/frontend.md`.
- **Qualidade:** Siga os padrões de `agents/clean-code.md`.

--------------------------------------------------------------------------------