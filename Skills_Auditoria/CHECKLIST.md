# AUDITORIA RÁPIDA — Comanda Digital Multi-Tenant

## 🔴 CRÍTICO (falha = brecha de segurança grave)
- [ ] Toda query SELECT tem `AND restaurant_id = %s`?
- [ ] Toda query UPDATE tem `AND restaurant_id = %s`?
- [ ] Toda query DELETE tem `AND restaurant_id = %s`?
- [ ] `restaurant_id` vem SEMPRE do JWT, nunca do body/query?
- [ ] Existe teste que tenta acessar dado de outro tenant?

## 🟠 IMPORTANTE (falha = risco ou bug em produção)
- [ ] Todas as tabelas de negócio têm coluna `restaurant_id`?
- [ ] Há índice em `restaurant_id` em todas as tabelas?
- [ ] Senhas com bcrypt, custo >= 12?
- [ ] JWT com expiração definida?
- [ ] Credenciais do banco em `.env` (não no código)?
- [ ] `.env` está no `.gitignore`?

## 🟡 RECOMENDADO (falha = dívida técnica)
- [ ] Paginação em todas as listagens?
- [ ] Rate limiting nas rotas públicas?
- [ ] CORS restrito aos seus domínios?
- [ ] Logs de auditoria para ações críticas?
- [ ] Validação de input com Pydantic em todas as rotas?

## Teste manual rápido
1. Crie 2 restaurantes de teste (ID 1 e ID 2)
2. Crie um pedido no restaurante 1
3. Tente acessar esse pedido com o token do restaurante 2
4. Deve retornar 404 — se retornar 200, tem IDOR!
