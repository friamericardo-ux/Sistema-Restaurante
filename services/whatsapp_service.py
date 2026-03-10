# services/whatsapp_service.py
import urllib.parse
import json
from config import Config

class WhatsAppService:
    """Serviço para integração com WhatsApp - Gera links wa.me"""
    
    @staticmethod
    def formatar_mensagem_pedido(pedido, itens):
        """Formata mensagem bonita para WhatsApp"""
        from datetime import datetime
        
        data_hora = datetime.now().strftime("%d/%m/%Y às %H:%M")
        
        mensagem = f"""🍔 NOVO PEDIDO DELIVERY #{pedido['id']}
📅 {data_hora}

👤 CLIENTE:
{pedido['cliente_nome']}
📞 {pedido['cliente_telefone']}
📍 {pedido['cliente_endereco']}

📋 ITENS DO PEDIDO:
"""
        for item in itens:
            nome = item.get("nome", "Item")
            qtd = item.get("quantidade", 1)
            preco = float(item.get("preco", 0))
            subtotal = qtd * preco
            obs = item.get("observacao", "")
            obs_texto = f" ({obs})" if obs else ""
            mensagem += f"• {qtd}x {nome}{obs_texto} - R$ {subtotal:.2f}\n"
        
        taxa = float(pedido.get('taxa_entrega', 5.00))
        total = float(pedido['total'])
        subtotal_pedido = total - taxa
        
        mensagem += f"""
💵 RESUMO:
Subtotal: R$ {subtotal_pedido:.2f}
🛵 Entrega: R$ {taxa:.2f}
💰 TOTAL: R$ {total:.2f}

⏱️ Previsão: 40-50 min

Obrigado pela preferência! 🎉"""
        
        return mensagem.strip()
    
    @staticmethod
    def gerar_link_whatsapp(mensagem, numero_destino=None):
        """Gera link wa.me com mensagem codificada"""
        if numero_destino is None:
            numero_destino = Config.WHATSAPP_RESTAURANTE
        
        # Limpa o número (remove espaços, traços, parênteses)
        numero_limpo = ''.join(filter(str.isdigit, str(numero_destino)))
        
        # Garante código do país (55 para Brasil)
        if not numero_limpo.startswith('55'):
            numero_limpo = f'55{numero_limpo}'
        
        # Codifica mensagem para URL
        mensagem_codificada = urllib.parse.quote(mensagem)
        
        return f"https://wa.me/{numero_limpo}?text={mensagem_codificada}"
    
    @staticmethod
    def formatar_mensagem_mesa(mesa_numero, itens, total):
        """Formata mensagem para pedidos de mesa"""
        from datetime import datetime
        
        data_hora = datetime.now().strftime("%d/%m/%Y às %H:%M")
        
        mensagem = f"""🍽️ PEDIDO MESA {mesa_numero}
📅 {data_hora}

📋 ITENS:
"""
        for item in itens:
            nome = item.get("nome", "Item")
            qtd = item.get("quantidade", 1)
            preco = float(item.get("preco", 0))
            subtotal = qtd * preco
            obs = item.get("observacao", "")
            obs_texto = f" ({obs})" if obs else ""
            mensagem += f"• {qtd}x {nome}{obs_texto} - R$ {subtotal:.2f}\n"
        
        mensagem += f"""
💰 TOTAL: R$ {total:.2f}

Pedido enviado da comanda digital! ✅"""
        
        return mensagem.strip()