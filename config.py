 # config.py
import os
from dotenv import load_dotenv

load_dotenv()
    
class Config:
    # Chave secreta para sessões
    SECRET_KEY = os.getenv('SECRET_KEY', 'sua-chave-secreta-mude-isso')
    
    # Configurações do Admin
    ADMIN_USER = os.getenv('ADMIN_USER', 'admin')
    ADMIN_PASS = os.getenv('ADMIN_PASS', 'admin123')
    
    # WhatsApp do Restaurante (configure com SEU número!)
    WHATSAPP_RESTAURANTE = os.getenv('WHATSAPP_RESTAURANTE', '5567993487509')
    
    # Taxa de entrega padrão
    TAXA_ENTREGA = float(os.getenv('TAXA_ENTREGA', '5.00'))
    
    # CAMINHO DO BANCO DE DADOS
    DB_PATH = os.getenv('DATABASE_URL', 'data/database.db')

    # Google Maps API
    GOOGLE_MAPS_KEY = os.getenv('GOOGLE_MAPS_API_KEY', '')
    RESTAURANTE_LAT = float(os.getenv('RESTAURANTE_LAT', '-20.4697'))
    RESTAURANTE_LNG = float(os.getenv('RESTAURANTE_LNG', '-54.6201'))
    FRETE_POR_KM = float(os.getenv('FRETE_POR_KM', '2.00'))

    # Evolution API (WhatsApp Robot)
    EVOLUTION_API_URL = os.getenv('EVOLUTION_API_URL', 'https://evolution.pantanaldev.com.br')
    EVOLUTION_API_KEY = os.getenv('EVOLUTION_API_KEY', '')
    N8N_WEBHOOK_URL = os.getenv('N8N_WEBHOOK_URL', 'https://n8n.pantanaldev.com.br/webhook/comanda-digital')


