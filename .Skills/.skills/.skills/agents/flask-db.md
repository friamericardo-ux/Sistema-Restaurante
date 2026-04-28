# Especialista em Flask & SQLAlchemy (DB)

## 1. Gestão de Migrações (Flask-Migrate/Alembic)
- **Nunca** altere o banco manualmente. Use sempre:
  - `flask db migrate -m "descrição"` para gerar scripts.
  - `flask db upgrade` para aplicar.
- **Rollback:** Antes de migrações críticas, gere o script de retorno.
- **Integridade:** Verifique chaves estrangeiras e índices para evitar orfandade de dados (A08:2026) [7].

## 2. Padrões de Consulta
- **Prepared Statements:** Use obrigatoriamente o SQLAlchemy ORM. Proiba concatenação de strings em queries para evitar SQL Injection (A03:2026) [6].
- **Tratamento de Erros:** Use blocos `try-except` granulares. Capture `SQLAlchemyError` e retorne mensagens genéricas ao usuário para não expor a estrutura do banco.

## 3. Segurança de Dados
- **Hashing:** Senhas devem usar **Argon2** ou **bcrypt**. Nunca armazene em texto puro [8].

--------------------------------------------------------------------------------