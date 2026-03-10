
from datetime import datetime
from models.item import Item

class Mesa:
    def _init_(self, numero):
        self.numero   = numero          # Ex: 5
        self.itens    = []              # Lista vazia de itens
        self.aberta   = True            # Mesa começa aberta
        self.abertura = datetime.now()  # Hora que abriu
        self.atendente = ""             # Nome da atendente

    @property
    def total(self):
        # Soma o subtotal de todos os itens
        return round(sum(item.subtotal for item in self.itens), 2)

    def adicionar_item(self, item):
        self.itens.append(item)  # Adiciona item na lista

    def remover_item(self, produto_id):
        # Percorre a lista de trás pra frente
        for i in range(len(self.itens) - 1, -1, -1):
            if self.itens[i].produto_id == produto_id:
                self.itens.pop(i)  # Remove o item
                return True
        return False  # Não encontrou

    def fechar(self):
        self.aberta = False  # Fecha a mesa

    def to_dict(self):
        return {
            "numero":    self.numero,
            "atendente": self.atendente,
            "abertura":  self.abertura.strftime("%d/%m/%Y %H:%M"),
            "itens":     [item.to_dict() for item in self.itens],
            "total":     self.total,
            "aberta":    self.aberta,
        }