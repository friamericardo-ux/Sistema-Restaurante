CARDAPIO = {
    "Lanches": [
        {"id": "L001", "nome": "X-Burguer",     "preco": 18.00},
        {"id": "L002", "nome": "X-Bacon",        "preco": 22.00},
        {"id": "L003", "nome": "X-Salada",       "preco": 20.00},
        {"id": "L004", "nome": "Hot Dog",         "preco": 15.00},
    ],
    "Bebidas": [
        {"id": "B001", "nome": "Refrigerante",   "preco": 7.00},
        {"id": "B002", "nome": "Suco Natural",   "preco": 10.00},
        {"id": "B003", "nome": "Água",           "preco": 4.00},
        {"id": "B004", "nome": "Cerveja 600ml",  "preco": 14.00},
    ],
    "Porções": [
        {"id": "P001", "nome": "Batata Frita",   "preco": 12.00},
        {"id": "P002", "nome": "Frango à Passarinho", "preco": 18.00},
        {"id": "P003", "nome": "Calabresa Acebolada", "preco": 15.00},
        {"id": "P004", "nome": "Mandioca Frita",  "preco": 10.00},  
    ]
}

def buscar_produto_por_id(produto_id):  
    for categoria, produtos in CARDAPIO.items():
        for produto in produtos:
            if produto["id"] == produto_id:
                return produto
    return None
