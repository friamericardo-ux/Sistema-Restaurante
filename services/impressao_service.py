import json
import logging
from data.db import get_connection, is_mysql

logger = logging.getLogger(__name__)

VID_PID_LIST = [
    (0x0483, 0x5740),
    (0x0416, 0x5011),
    (0x04b8, 0x0202),
]


def _conectar_usb():
    from escpos.printer import Usb
    from escpos.exceptions import DeviceNotFoundError

    for vid, pid in VID_PID_LIST:
        try:
            p = Usb(vid, pid)
            logger.info(f"Conectado impressora VID=0x{vid:04x} PID=0x{pid:04x}")
            return p
        except DeviceNotFoundError:
            continue
        except Exception as e:
            logger.debug(f"Falha VID=0x{vid:04x} PID=0x{pid:04x}: {e}")
            continue
    return None


def imprimir_comanda(pedido_id, restaurante_id=1):
    db = get_connection()
    cursor = db.cursor()
    ph = "%s" if is_mysql() else "?"

    cursor.execute(
        f"SELECT id, cliente_nome, cliente_telefone, cliente_endereco, itens, "
        f"taxa_entrega, total, forma_pagamento, troco, status, criado_em "
        f"FROM pedidos_delivery WHERE id = {ph} AND restaurante_id = {ph}",
        (pedido_id, restaurante_id)
    )
    pedido = cursor.fetchone()
    if not pedido:
        db.close()
        raise ValueError("Pedido nao encontrado")

    dados = {
        "id": pedido[0],
        "cliente_nome": pedido[1] or "",
        "cliente_telefone": pedido[2] or "",
        "cliente_endereco": pedido[3] or "",
        "itens": json.loads(pedido[4]) if pedido[4] else [],
        "taxa_entrega": float(pedido[5] or 0),
        "total": float(pedido[6] or 0),
        "forma_pagamento": pedido[7] or "",
        "troco": float(pedido[8] or 0),
    }

    cursor.execute(
        f"SELECT valor FROM configuracoes WHERE chave = {ph} AND restaurante_id = {ph}",
        ("nome_restaurante", restaurante_id)
    )
    row = cursor.fetchone()
    nome = row[0] if row else "Comanda Digital"
    db.close()

    printer = _conectar_usb()
    if printer is None:
        raise ConnectionError("Impressora nao encontrada. Conecte o cabo USB.")

    try:
        _formatar(printer, nome, dados)
    finally:
        try:
            printer.close()
        except Exception:
            pass


def _formatar(p, nome_restaurante, d):
    itens = d["itens"]
    total = d["total"]
    pgto = d["forma_pagamento"]
    troco = d["troco"]
    pedido_id = d["id"]
    criado = d["criado_em"]

    label_pgto = {
        "pix": "PIX", "dinheiro": "Dinheiro", "credito": "Cartao Credito",
        "cartao_credito": "Cartao Credito", "debito": "Cartao Debito",
        "cartao_debito": "Cartao Debito", "cartao": "Cartao",
    }

    L = 32

    p.set(align="center", bold=True, height=2, width=1)
    p.text(f"{nome_restaurante}\n")
    p.set(align="center", bold=False, height=1, width=1)
    p.text("=" * L + "\n")

    p.set(align="center", bold=True)
    p.text(f"PEDIDO #{pedido_id}\n")
    p.set(align="center", bold=False)
    p.text(f"{criado}\n")
    p.text("=" * L + "\n")

    nome = d["cliente_nome"]
    fone = d["cliente_telefone"]
    ender = d["cliente_endereco"]
    if nome or fone or ender:
        p.set(align="left", bold=True)
        p.text(f"{'CLIENTE':^{L}}\n")
        p.set(align="left", bold=False)
        if nome:
            p.text(f"{nome}\n")
        if fone:
            p.text(f"Tel: {fone}\n")
        p.text("-" * L + "\n")

    p.set(align="left", bold=True)
    p.text(f"{'ITENS':^{L}}\n")
    p.set(align="left", bold=False)
    p.text("-" * L + "\n")

    for item in itens:
        qtd = item.get("quantidade", 1)
        nome_i = item.get("nome", "Item")
        preco = float(item.get("preco", 0))
        sub = qtd * preco

        rotulo = f"{qtd}x {nome_i}"
        if len(rotulo) > 22:
            rotulo = rotulo[:21] + "."
        linha = f"{rotulo:<22} R${sub:>5.2f}"
        p.text(f"{linha}\n")

        adicionais = item.get("adicionais", [])
        if adicionais:
            if isinstance(adicionais, str):
                p.text(f"  +{adicionais}\n")
            elif isinstance(adicionais, list):
                parts = []
                for a in adicionais:
                    if isinstance(a, dict):
                        parts.append(a.get("nome", ""))
                    else:
                        parts.append(str(a))
                if parts:
                    p.text(f"  +{', '.join(parts)}\n")

        obs = item.get("observacao", "")
        if obs:
            p.text(f"  Obs: {obs}\n")

    p.text("-" * L + "\n")

    sub_total = sum(
        float(i.get("preco", 0)) * i.get("quantidade", 1) for i in itens
    )
    taxa = d["taxa_entrega"]

    p.set(align="left", bold=False, height=1, width=1)
    p.text(f"{'Subtotal':<22} R${sub_total:>5.2f}\n")
    if taxa > 0:
        p.text(f"{'Taxa entrega':<22} R${taxa:>5.2f}\n")
    p.set(align="left", bold=True, height=2, width=1)
    p.text(f"{'TOTAL':<22} R${total:>5.2f}\n")

    p.set(align="left", bold=False, height=1, width=1)
    if pgto:
        lbl = label_pgto.get(pgto.lower(), pgto)
        p.text(f"Pagamento: {lbl}\n")
        if troco > 0:
            p.text(f"Troco: R$ {troco:.2f}\n")

    p.set(align="center")
    p.text("=" * L + "\n")
    p.text("Obrigado pela preferencia!\n")
    p.text("\n\n")
    p.cut()
