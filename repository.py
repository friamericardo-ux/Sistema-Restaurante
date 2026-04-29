from config import Config
from models.user import User
from security import SecurityService
from typing import Optional
from data.db import get_connection, is_mysql


class UserRepository:
    def __init__(self):
        self.db_path = Config.DB_PATH

    def get_connection(self):
        return get_connection()

    def init_user_table(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        if is_mysql():
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INT PRIMARY KEY AUTO_INCREMENT,
                    username VARCHAR(100) UNIQUE NOT NULL,
                    password_hash VARCHAR(255) NOT NULL,
                    role VARCHAR(50) DEFAULT 'admin'
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
        else:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    role TEXT DEFAULT 'admin'
                )
            """)
        # Migração: adiciona licenca_vencimento se não existir
        if is_mysql():
            try:
                cursor.execute("ALTER TABLE users ADD COLUMN licenca_vencimento DATE DEFAULT NULL")
                conn.commit()
            except Exception:
                pass  # coluna já existe
        else:
            try:
                cursor.execute("ALTER TABLE users ADD COLUMN licenca_vencimento TEXT DEFAULT NULL")
                conn.commit()
            except Exception:
                pass  # coluna já existe

    def create_admin(self):
        self.init_user_table()
        conn = self.get_connection()
        cursor = conn.cursor()
        ph = "%s" if is_mysql() else "?"
        cursor.execute(f"SELECT id FROM users WHERE username = {ph}", (Config.ADMIN_USER,))
        if cursor.fetchone():
            return False
        password_hash = SecurityService.hash_password(Config.ADMIN_PASS)
        cursor.execute(
            f"INSERT INTO users (username, password_hash, role) VALUES ({ph}, {ph}, {ph})",
            (Config.ADMIN_USER, password_hash, "admin")
        )
        conn.commit()
        return True

    def has_any_user(self) -> bool:
        self.init_user_table()
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM users LIMIT 1")
        return cursor.fetchone() is not None

    def create_custom_admin(self, username: str, password: str, restaurante_id: int = 1, role: str = 'admin') -> bool:
        self.init_user_table()
        ph = "%s" if is_mysql() else "?"
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(f"SELECT id FROM users WHERE username = {ph}", (username,))
        if cursor.fetchone():
            return False
        password_hash = SecurityService.hash_password(password)
        cursor.execute(
            f"INSERT INTO users (username, password_hash, role, restaurante_id) VALUES ({ph}, {ph}, {ph}, {ph})",
            (username, password_hash, role, restaurante_id)
        )
        conn.commit()
        return True

    def get_user_by_username(self, username: str) -> Optional[User]:
        ph = "%s" if is_mysql() else "?"
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            f"SELECT id, username, password_hash, role, restaurante_id FROM users WHERE username = {ph}",
            (username,)
        )
        row = cursor.fetchone()
        conn.close()
        if row:
            return User(id=row[0], username=row[1], password_hash=row[2], role=row[3], restaurante_id=row[4])
        return None

    def update_password(self, user_id: int, new_password: str) -> None:
        ph = "%s" if is_mysql() else "?"
        new_hash = SecurityService.hash_password(new_password)
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            f"UPDATE users SET password_hash = {ph} WHERE id = {ph}",
            (new_hash, user_id)
        )
        conn.commit()
        conn.close()

    def list_users(self, restaurante_id: int):
        self.init_user_table()
        conn = self.get_connection()
        cursor = conn.cursor()
        ph = "%s" if is_mysql() else "?"
        cursor.execute(
            f"SELECT id, username, role FROM users WHERE restaurante_id = {ph} AND role != 'superadmin' ORDER BY id",
            (restaurante_id,)
        )
        rows = cursor.fetchall()
        conn.close()
        return rows

    def delete_user(self, user_id: int, current_user_id: int, restaurante_id: int) -> bool:
        if user_id == current_user_id:
            return False
        ph = "%s" if is_mysql() else "?"
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            f"SELECT id FROM users WHERE id = {ph} AND restaurante_id = {ph} AND role != 'superadmin'",
            (user_id, restaurante_id)
        )
        if not cursor.fetchone():
            conn.close()
            return False
        cursor.execute(f"DELETE FROM users WHERE id = {ph}", (user_id,))
        conn.commit()
        conn.close()
        return True

    def list_admins(self):
        """Lista todos os usuários com role != superadmin (para o painel superadmin)."""
        self.init_user_table()
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, username, role, licenca_vencimento
            FROM users
            WHERE role != 'superadmin' AND role != 'super_admin'
            ORDER BY id
        """)
        rows = cursor.fetchall()
        conn.close()
        return rows

    def renovar_licenca(self, user_id: int, dias: int) -> bool:
        """Renova a licença somando X dias. Se vencida, conta a partir de hoje."""
        from datetime import date, timedelta
        ph = "%s" if is_mysql() else "?"
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(f"SELECT licenca_vencimento FROM users WHERE id = {ph}", (user_id,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            return False
        vencimento_atual = row[0]
        hoje = date.today()
        if vencimento_atual:
            venc = vencimento_atual if isinstance(vencimento_atual, date) else date.fromisoformat(str(vencimento_atual))
            nova_data = venc + timedelta(days=dias) if venc > hoje else hoje + timedelta(days=dias)
        else:
            nova_data = hoje + timedelta(days=dias)
        
        cursor.execute(f"UPDATE users SET licenca_vencimento = {ph} WHERE id = {ph}", (nova_data if is_mysql() else str(nova_data), user_id))
        conn.commit()
        conn.close()
        return True

    def bloquear_licenca(self, user_id: int) -> bool:
        """Define vencimento como ontem (bloqueia imediatamente)."""
        from datetime import date, timedelta
        ph = "%s" if is_mysql() else "?"
        ontem = date.today() - timedelta(days=1)
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(f"UPDATE users SET licenca_vencimento = {ph} WHERE id = {ph}", (ontem if is_mysql() else str(ontem), user_id))
        conn.commit()
        conn.close()
        return True


# ========== DASHBOARD ==========

def obter_resumo_dashboard(restaurante_id):
    """
    Retorna os dados consolidados para o dashboard.
    """
    ph = "%s" if is_mysql() else "?"
    conn = get_connection()
    cursor = conn.cursor()
    try:
        # 1. Mesas abertas
        cursor.execute(f"SELECT COUNT(*) FROM mesas WHERE restaurante_id = {ph}", (restaurante_id,))
        mesas_abertas = cursor.fetchone()[0] or 0

        # 2. Pedidos delivery por status (não entregues)
        cursor.execute(f"""
            SELECT status, COUNT(*) 
            FROM pedidos_delivery
            WHERE status != 'entregue' AND restaurante_id = {ph}
            GROUP BY status
        """, (restaurante_id,))
        pedidos_por_status = {row[0]: row[1] for row in cursor.fetchall()}

        # 3. Verificar se o caixa já foi fechado hoje
        if is_mysql():
            cursor.execute(f"SELECT id FROM caixa_fechamentos WHERE DATE(criado_em) = CURDATE() AND restaurante_id = {ph} LIMIT 1", (restaurante_id,))
        else:
            cursor.execute(f"SELECT id FROM caixa_fechamentos WHERE DATE(criado_em, 'localtime') = DATE('now', 'localtime') AND restaurante_id = {ph} LIMIT 1", (restaurante_id,))
        caixa_fechado = cursor.fetchone() is not None

        pedidos_hoje = 0
        faturamento_hoje = 0.0

        if not caixa_fechado:
            # 4. Total de pedidos hoje
            if is_mysql():
                cursor.execute(f"SELECT COUNT(*) FROM pedidos_delivery WHERE DATE(criado_em) = CURDATE() AND restaurante_id = {ph}", (restaurante_id,))
            else:
                cursor.execute(f"SELECT COUNT(*) FROM pedidos_delivery WHERE DATE(criado_em, 'localtime') = DATE('now', 'localtime') AND restaurante_id = {ph}", (restaurante_id,))
            pedidos_hoje = cursor.fetchone()[0] or 0

            # 5. Faturamento hoje (entregues)
            if is_mysql():
                cursor.execute(f"SELECT SUM(total) FROM pedidos_delivery WHERE DATE(criado_em) = CURDATE() AND status = 'entregue' AND restaurante_id = {ph}", (restaurante_id,))
            else:
                cursor.execute(f"SELECT SUM(total) FROM pedidos_delivery WHERE DATE(criado_em, 'localtime') = DATE('now', 'localtime') AND status = 'entregue' AND restaurante_id = {ph}", (restaurante_id,))
            res_fat = cursor.fetchone()[0]
            faturamento_hoje = float(res_fat) if res_fat else 0.0
            
        return {
            "mesas_abertas": mesas_abertas,
            "pedidos_novos": pedidos_por_status.get("novo", 0),
            "pedidos_preparo": pedidos_por_status.get("em_preparo", 0),
            "pedidos_entrega": pedidos_por_status.get("saiu_entrega", 0),
            "pedidos_hoje": pedidos_hoje,
            "faturamento_hoje": faturamento_hoje
        }
    finally:
        conn.close()


# ========== MESAS ==========

def listar_mesas_com_itens(restaurante_id):
    """Lista mesas abertas e seus respectivos itens."""
    ph = "%s" if is_mysql() else "?"
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(f"SELECT id, numero, total, status FROM mesas WHERE restaurante_id = {ph}", (restaurante_id,))
        mesas_db = cursor.fetchall()

        mesas = []
        cursor2 = conn.cursor()
        for mesa in mesas_db:
            cursor2.execute(
                f"SELECT id, nome, preco, quantidade, observacao FROM itens WHERE mesa_id = {ph} AND restaurante_id = {ph}",
                (mesa[0], restaurante_id)
            )
            itens = []
            for i in cursor2.fetchall():
                itens.append({
                    "id": i[0],
                    "nome": i[1],
                    "preco": float(i[2]),
                    "quantidade": i[3],
                    "observacao": i[4]
                })

            mesas.append({
                "id": mesa[0],
                "numero": mesa[1],
                "total": float(mesa[2]),
                "status": mesa[3] or "livre",
                "itens": itens
            })
        return mesas
    finally:
        conn.close()

def abrir_mesa(numero, restaurante_id):
    ph = "%s" if is_mysql() else "?"
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(f"SELECT id FROM mesas WHERE numero = {ph} AND restaurante_id = {ph}", (numero, restaurante_id))
        if cursor.fetchone():
            return False, "Mesa já está aberta!"
        
        cursor.execute(
            f"INSERT INTO mesas (numero, total, status, restaurante_id) VALUES ({ph}, {ph}, {ph}, {ph})",
            (numero, 0.0, "aberta", restaurante_id)
        )
        conn.commit()
        return True, None
    finally:
        conn.close()

def adicionar_item_mesa(mesa_numero, nome, preco, quantidade, observacao, restaurante_id):
    ph = "%s" if is_mysql() else "?"
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(f"SELECT id FROM mesas WHERE numero = {ph} AND restaurante_id = {ph}", (mesa_numero, restaurante_id))
        mesa = cursor.fetchone()
        if not mesa:
            return False, "Mesa não encontrada!"
        
        mesa_id = mesa[0]
        cursor.execute(f"""
            INSERT INTO itens (mesa_id, nome, preco, quantidade, observacao, restaurante_id)
            VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph})
        """, (mesa_id, nome, preco, quantidade, observacao, restaurante_id))

        # Atualiza total da mesa
        cursor.execute(f"SELECT SUM(preco * quantidade) FROM itens WHERE mesa_id = {ph} AND restaurante_id = {ph}", (mesa_id, restaurante_id))
        total = cursor.fetchone()[0] or 0
        cursor.execute(f"UPDATE mesas SET total = {ph} WHERE id = {ph} AND restaurante_id = {ph}", (total, mesa_id, restaurante_id))
        
        # Atualiza status para 'ocupada' se tem consumo e não está com conta pedida
        if total and float(total) > 0:
            cursor.execute(f"UPDATE mesas SET status = 'ocupada' WHERE id = {ph} AND restaurante_id = {ph} AND status != 'conta_pedida'", (mesa_id, restaurante_id))
        
        conn.commit()
        return True, None
    finally:
        conn.close()

def remover_item_mesa(item_id, restaurante_id):
    ph = "%s" if is_mysql() else "?"
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(f"SELECT mesa_id FROM itens WHERE id = {ph} AND restaurante_id = {ph}", (item_id, restaurante_id))
        row = cursor.fetchone()
        if not row:
            return False, "Item não encontrado!"
        
        mesa_id = row[0]
        cursor.execute(f"DELETE FROM itens WHERE id = {ph} AND restaurante_id = {ph}", (item_id, restaurante_id))

        # Atualiza total da mesa
        cursor.execute(f"SELECT SUM(preco * quantidade) FROM itens WHERE mesa_id = {ph} AND restaurante_id = {ph}", (mesa_id, restaurante_id))
        total = cursor.fetchone()[0] or 0
        cursor.execute(f"UPDATE mesas SET total = {ph} WHERE id = {ph} AND restaurante_id = {ph}", (total, mesa_id, restaurante_id))
        
        conn.commit()
        return True, None
    finally:
        conn.close()

def fechar_mesa_com_historico(mesa_numero, restaurante_id):
    import json
    ph = "%s" if is_mysql() else "?"
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(f"SELECT id, numero, total FROM mesas WHERE numero = {ph} AND restaurante_id = {ph}", (mesa_numero, restaurante_id))
        mesa = cursor.fetchone()
        if not mesa:
            return False, "Mesa não encontrada!"
        
        mesa_id = mesa[0]
        # Busca itens para o histórico
        cursor.execute(f"SELECT nome, preco, quantidade, observacao FROM itens WHERE mesa_id = {ph} AND restaurante_id = {ph}", (mesa_id, restaurante_id))
        itens_db = cursor.fetchall()
        itens_list = [{"nome": i[0], "preco": float(i[1]), "quantidade": i[2], "observacao": i[3]} for i in itens_db]
        itens_json = json.dumps(itens_list, ensure_ascii=False)

        # Salva no histórico
        cursor.execute(f"""
            INSERT INTO historico_mesas (mesa_numero, total, itens, restaurante_id) 
            VALUES ({ph}, {ph}, {ph}, {ph})
        """, (mesa[1], float(mesa[2]), itens_json, restaurante_id))

        # Deleta mesa e itens
        cursor.execute(f"DELETE FROM itens WHERE mesa_id = {ph} AND restaurante_id = {ph}", (mesa_id, restaurante_id))
        cursor.execute(f"DELETE FROM mesas WHERE id = {ph} AND restaurante_id = {ph}", (mesa_id, restaurante_id))
        
        conn.commit()
        return True, None
    finally:
        conn.close()

def get_mesa(mesa_id, restaurante_id):
    ph = "%s" if is_mysql() else "?"
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(f"SELECT id, numero, total, status FROM mesas WHERE id = {ph} AND restaurante_id = {ph}", (mesa_id, restaurante_id))
        row = cursor.fetchone()
        if not row:
            return None
        return {
            "id": row[0],
            "numero": row[1],
            "total": float(row[2]),
            "status": row[3] or "livre"
        }
    finally:
        conn.close()

def pedir_conta_mesa(mesa_id, restaurante_id):
    ph = "%s" if is_mysql() else "?"
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(f"SELECT id, status FROM mesas WHERE id = {ph} AND restaurante_id = {ph}", (mesa_id, restaurante_id))
        mesa = cursor.fetchone()
        if not mesa:
            return False, "Mesa não encontrada!"
        
        cursor.execute(f"UPDATE mesas SET status = {ph} WHERE id = {ph} AND restaurante_id = {ph}", ("conta_pedida", mesa_id, restaurante_id))
        conn.commit()
        return True, None
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        conn.close()

def fechar_mesa(mesa_id, restaurante_id):
    import json
    ph = "%s" if is_mysql() else "?"
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(f"SELECT id, numero, total FROM mesas WHERE id = {ph} AND restaurante_id = {ph}", (mesa_id, restaurante_id))
        mesa = cursor.fetchone()
        if not mesa:
            return False, "Mesa não encontrada!"
        
        mesa_id_val = mesa[0]
        cursor.execute(f"SELECT nome, preco, quantidade, observacao FROM itens WHERE mesa_id = {ph} AND restaurante_id = {ph}", (mesa_id_val, restaurante_id))
        itens_db = cursor.fetchall()
        itens_list = [{"nome": i[0], "preco": float(i[1]), "quantidade": i[2], "observacao": i[3]} for i in itens_db]
        itens_json = json.dumps(itens_list, ensure_ascii=False)

        cursor.execute(f"""
            INSERT INTO historico_mesas (mesa_numero, total, itens, restaurante_id) 
            VALUES ({ph}, {ph}, {ph}, {ph})
        """, (mesa[1], float(mesa[2]), itens_json, restaurante_id))

        cursor.execute(f"DELETE FROM itens WHERE mesa_id = {ph} AND restaurante_id = {ph}", (mesa_id_val, restaurante_id))
        cursor.execute(f"DELETE FROM mesas WHERE id = {ph} AND restaurante_id = {ph}", (mesa_id_val, restaurante_id))
        
        conn.commit()
        return True, None
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        conn.close()


# ========== PRODUTOS ==========

def listar_produtos(restaurante_id):
    ph = "%s" if is_mysql() else "?"
    conn = get_connection()
    cursor = conn.cursor()
    # Ordem fixa: id(0), nome(1), preco(2), categoria(3), emoji(4), foto(5), descricao(6)
    cursor.execute(f"SELECT id, nome, preco, categoria, emoji, foto, descricao FROM produtos WHERE ativo = 1 AND restaurante_id = {ph}", (restaurante_id,))
    rows = cursor.fetchall()
    conn.close()
    return rows

def adicionar_produto(nome, preco, categoria, emoji, restaurante_id, foto=None, descricao=None):
    ph = "%s" if is_mysql() else "?"
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        f"INSERT INTO produtos (nome, preco, categoria, emoji, foto, descricao, restaurante_id) VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph})",
        (nome, preco, categoria, emoji, foto, descricao, restaurante_id)
    )
    conn.commit()
    conn.close()

def editar_produto(id, nome, preco, categoria, emoji, restaurante_id, foto=None):
    ph = "%s" if is_mysql() else "?"
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        f"UPDATE produtos SET nome={ph}, preco={ph}, categoria={ph}, emoji={ph}, foto={ph} WHERE id={ph} AND restaurante_id={ph}",
        (nome, preco, categoria, emoji, foto, id, restaurante_id)
    )
    conn.commit()
    conn.close()

def desativar_produto(id, restaurante_id):
    ph = "%s" if is_mysql() else "?"
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(f"UPDATE produtos SET ativo = 0 WHERE id = {ph} AND restaurante_id = {ph}", (id, restaurante_id))
    conn.commit()
    conn.close()

def listar_categorias_produtos(restaurante_id):
    """Retorna lista de categorias únicas dos produtos ativos."""
    ph = "%s" if is_mysql() else "?"
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(f"SELECT DISTINCT categoria FROM produtos WHERE ativo = 1 AND restaurante_id = {ph} ORDER BY categoria", (restaurante_id,))
    rows = cursor.fetchall()
    conn.close()
    return [row[0] for row in rows]


# ========== ADICIONAIS ==========

def listar_adicionais(restaurante_id, categoria=None):
    """
    Lista adicionais ativos.
    Se categoria informada, retorna só os vinculados àquela categoria.
    """
    ph = "%s" if is_mysql() else "?"
    conn = get_connection()
    cursor = conn.cursor()
    if categoria:
        cursor.execute(f"""
            SELECT a.id, a.nome, a.preco
            FROM adicionais a
            INNER JOIN adicional_categoria ac ON a.id = ac.adicional_id
            WHERE a.ativo = 1 AND a.restaurante_id = {ph} AND ac.categoria = {ph}
        """, (restaurante_id, categoria))
    else:
        cursor.execute(f"SELECT id, nome, preco FROM adicionais WHERE ativo = 1 AND restaurante_id = {ph}", (restaurante_id,))
    rows = cursor.fetchall()
    conn.close()
    return rows

def listar_adicionais_com_categorias(restaurante_id):
    """Lista todos os adicionais com suas categorias vinculadas (para o painel admin)."""
    ph = "%s" if is_mysql() else "?"
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(f"SELECT id, nome, preco, ativo FROM adicionais WHERE restaurante_id = {ph} ORDER BY nome", (restaurante_id,))
    adicionais = cursor.fetchall()

    resultado = []
    cursor2 = conn.cursor()
    for a in adicionais:
        cursor2.execute(
            f"SELECT categoria FROM adicional_categoria WHERE adicional_id = {ph}", (a[0],)
        )
        categorias = [row[0] for row in cursor2.fetchall()]
        resultado.append({
            "id": a[0],
            "nome": a[1],
            "preco": float(a[2]),
            "ativo": a[3],
            "categorias": categorias
        })
    conn.close()
    return resultado

def adicionar_adicional(nome, preco, categorias: list, restaurante_id):
    """
    Cadastra um adicional e vincula às categorias informadas.
    """
    ph = "%s" if is_mysql() else "?"
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        f"INSERT INTO adicionais (nome, preco, restaurante_id) VALUES ({ph}, {ph}, {ph})",
        (nome, preco, restaurante_id)
    )
    adicional_id = cursor.lastrowid
    for cat in categorias:
        cursor.execute(
            f"INSERT INTO adicional_categoria (adicional_id, categoria, restaurante_id) VALUES ({ph}, {ph}, {ph})",
            (adicional_id, cat, restaurante_id)
        )
    conn.commit()
    conn.close()
    return adicional_id

def editar_adicional(id, nome, preco, categorias: list, restaurante_id):
    """Atualiza nome/preço e recadastra as categorias vinculadas."""
    ph = "%s" if is_mysql() else "?"
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        f"UPDATE adicionais SET nome={ph}, preco={ph} WHERE id={ph} AND restaurante_id={ph}",
        (nome, preco, id, restaurante_id)
    )
    cursor.execute(f"DELETE FROM adicional_categoria WHERE adicional_id = {ph} AND restaurante_id = {ph}", (id, restaurante_id))
    for cat in categorias:
        cursor.execute(
            f"INSERT INTO adicional_categoria (adicional_id, categoria, restaurante_id) VALUES ({ph}, {ph}, {ph})",
            (id, cat, restaurante_id)
        )
    conn.commit()
    conn.close()

def desativar_adicional(id, restaurante_id):
    ph = "%s" if is_mysql() else "?"
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(f"UPDATE adicionais SET ativo = 0 WHERE id = {ph} AND restaurante_id = {ph}", (id, restaurante_id))
    conn.commit()
    conn.close()


# ========== PEDIDOS DELIVERY ==========

def criar_pedido_delivery(dados):
    """Cria um novo pedido delivery no banco."""
    import json
    ph = "%s" if is_mysql() else "?"
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cliente_nome = dados.get("nome")
        cliente_telefone = dados.get("telefone")
        cliente_endereco = dados.get("endereco")
        itens = dados.get("itens", [])
        forma_pagamento = (dados.get("pagamento") or "").strip().lower()
        troco = float(dados.get("troco") or 0)
        restaurante_id = int(dados.get("restaurante_id") or 1)
        taxa_entrega = float(dados.get("taxa_entrega") or 0)

        total = sum(float(item.get("preco", 0)) * int(item.get("quantidade", 1)) for item in itens)
        total += taxa_entrega

        cursor.execute(f"""
            INSERT INTO pedidos_delivery
            (cliente_nome, cliente_telefone, cliente_endereco, itens, taxa_entrega, total, forma_pagamento, troco, status, restaurante_id)
            VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph})
        """, (
            cliente_nome, cliente_telefone, cliente_endereco,
            json.dumps(itens, ensure_ascii=False),
            taxa_entrega, total, forma_pagamento, troco, 'novo', restaurante_id
        ))
        
        pedido_id = cursor.lastrowid
        conn.commit()
        return {
            "pedido_id": pedido_id,
            "total": total,
            "itens": itens,
            "cliente": cliente_nome,
            "taxa_entrega": taxa_entrega
        }
    finally:
        conn.close()