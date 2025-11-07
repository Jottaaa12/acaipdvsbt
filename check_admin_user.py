import sqlite3
import os

# Caminho do banco de dados
db_path = os.path.join(os.path.expanduser("~"), "AppData", "Roaming", "PDV Moderno", "pdv.db")

if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Verificar usuários
    cursor.execute("SELECT id, username, role, active, is_deleted FROM users WHERE is_deleted = 0")
    users = cursor.fetchall()

    print("Usuários encontrados:")
    for user in users:
        print(f"ID: {user[0]}, Username: {user[1]}, Role: {user[2]}, Active: {user[3]}, Deleted: {user[4]}")

    # Verificar especificamente o usuário admin
    cursor.execute("SELECT id, username, password_hash, role, active FROM users WHERE username = 'admin' AND is_deleted = 0")
    admin_user = cursor.fetchone()

    if admin_user:
        print(f"\nUsuário admin encontrado:")
        print(f"ID: {admin_user[0]}")
        print(f"Username: {admin_user[1]}")
        print(f"Password Hash: {admin_user[2][:32]}...")
        print(f"Role: {admin_user[3]}")
        print(f"Active: {admin_user[4]}")
    else:
        print("\nUsuário admin não encontrado!")

    conn.close()
else:
    print(f"Banco de dados não encontrado em: {db_path}")
