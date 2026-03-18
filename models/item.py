
class Item:
    def __init__(self, produto_id, nome, preco, quantidade, obs=""):
        self.produto_id = produto_id  # Ex: "P001"
        self.nome       = nome        # Ex: "Batata Frita"
        self.preco      = preco       # Ex: 12.00
        self.quantidade = quantidade  # Ex: 2
        self.obs        = obs         # Ex: "sem sal"

    @property
    def subtotal(self):
        # Calcula: preço × quantidade
        return round(self.preco * self.quantidade, 2)

    def to_dict(self):
        # Transforma o item em dicionário para salvar/enviar
        return {
            "produto_id": self.produto_id,
            "nome":       self.nome,
            "preco":      self.preco,
            "quantidade": self.quantidade,
            "obs":        self.obs,
            "subtotal":   self.subtotal,
        }