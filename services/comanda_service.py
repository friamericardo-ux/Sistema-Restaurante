
import json
import os
from models.mesa import Mesa
from models.item import Item
from data.cardapio import buscar_produto_por_id

ARQUIVO_PEDIDOS = "data/pedidos_salvos.json"

class ComandaService:
    def _init_(self):
        self.mesas = {}  # {numero: Mesa}

    def abrir_mesa(self, numero, atendente=""):
        try:
            if numero in self.mesas and self.mesas[numero].aberta:
                return self.mesas[numero]
            mesa = Mesa(numero)
            mesa.atendente = atendente
            self.mesas[numero] = mesa
            return mesa
        except Exception as e:
            raise RuntimeError(f"Erro ao abrir mesa: {e}")

    def obter_mesa(self, numero):
        return self.mesas.get(numero)

    def listar_mesas(self):
        return [m.to_dict() for m in self.mesas.values() if m.aberta]

    def adicionar_item(self, numero_mesa, produto_id, quantidade=1, obs=""):
        try:
            mesa = self.mesas.get(numero_mesa)
            if not mesa:
                raise ValueError(f"Mesa {numero_mesa} não encontrada.")
            produto = buscar_produto_por_id(produto_id)
            if not produto:
                raise ValueError(f"Produto {produto_id} não encontrado.")
            item = Item(
                produto_id = produto["id"],
                nome       = produto["nome"],
                preco      = produto["preco"],
                quantidade = quantidade,
                obs        = obs
            )
            mesa.adicionar_item(item)
            return item
        except ValueError:
            raise
        except Exception as e:
            raise RuntimeError(f"Erro ao adicionar item: {e}")

    def fechar_mesa(self, numero):
        try:
            mesa = self.mesas.get(numero)
            if not mesa:
                raise ValueError(f"Mesa {numero} não encontrada.")
            mesa.fechar()
            resumo = mesa.to_dict()
            self._arquivar(resumo)
            del self.mesas[numero]
            return resumo
        except ValueError:
            raise
        except Exception as e:
            raise RuntimeError(f"Erro ao fechar mesa: {e}")

    def _arquivar(self, resumo):
        try:
            pedidos = []
            if os.path.exists(ARQUIVO_PEDIDOS):
                with open(ARQUIVO_PEDIDOS, "r", encoding="utf-8") as f:
                    pedidos = json.load(f)
            pedidos.append(resumo)
            with open(ARQUIVO_PEDIDOS, "w", encoding="utf-8") as f:
                json.dump(pedidos, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Aviso: não salvou o pedido: {e}")