from app import app, db

with app.app_context():
    print("A apagar tabelas antigas...")
    db.drop_all()  # Apaga TUDO do MySQL
    
    print("A criar tabelas novas...")
    db.create_all() # Cria as tabelas baseadas no teu código atual do app.py
    
    print("Sucesso! A Base de Dados está limpa e sincronizada.")