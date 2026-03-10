from PIL import Image
import os

# Criar pasta se não existir
os.makedirs('static/img/produtos', exist_ok=True)

print("Criando imagem de teste...")

# Criar imagem colorida (laranja)
img = Image.new('RGB', (200, 200), color='#f0a500')

# Salvar na pasta correta
img.save('static/img/produtos/lanche001.png')

# Verificar se salvou
if os.path.exists('static/img/produtos/lanche001.png'):
    tamanho = os.path.getsize('static/img/produtos/lanche001.png')
    print(f"✅ Imagem criada com sucesso!")
    print(f"📁 Local: static/img/produtos/lanche001.png")
    print(f"📦 Tamanho: {tamanho} bytes")
else:
    print("❌ Erro ao criar imagem")