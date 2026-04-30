# ═══════════════════════════════════════════════════════════════
#  LEGADO — NÃO USAR EM PRODUÇÃO
# ═══════════════════════════════════════════════════════════════
#
#  Este script está OBSOLETO e foi movido para:
#       legacy/criar_tabela.py
#
#  Motivo:
#       Cria schemas incorretos que divergem do schema oficial
#       definido em data/db.py + migrations.
#
#  Consequência conhecida:
#       - Coluna fantasma "nome" em adicional_categoria
#       - PK errada (id) em adicional_categoria
#       - Colunas faltando (restaurante_id, status, etc.)
#       - Nomes de coluna errados (imagem → foto, password → password_hash)
#
#  Use exclusivamente init_db() → _run_migrations() para criar/atualizar
#  o banco de dados.
#
# ═══════════════════════════════════════════════════════════════

import sys
print("=" * 70)
print("  ERRO: criar_tabela.py está OBSOLETO e NÃO deve ser usado.")
print("  Use init_db() → _run_migrations() para criar/atualizar o banco.")
print("  O arquivo original foi movido para: legacy/criar_tabela.py")
print("=" * 70)
sys.exit(1)
