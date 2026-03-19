from app import app, get_db
from security import SecurityService

with app.app_context():
    db = get_db()
    senha = SecurityService.hash_password('admin123')
    db.execute("INSERT INTO usuarios (nome, login, senha, role) VALUES ('Admin', 'admin', ?, 'admin')", [senha])
    db.commit()
    print('Admin criado!')