import sqlite3
import hashlib
from .connection import get_db_connection

def hash_password(password):
    """Gera hash da senha usando SHA-256."""
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(password, password_hash):
    """Verifica se a senha corresponde ao hash."""
    return hash_password(password) == password_hash

def authenticate_user(username, password):
    """Autentica usuário e retorna dados se válido."""
    conn = get_db_connection()
    user = conn.execute('''
        SELECT * FROM users 
        WHERE username = ? AND active = 1
    ''', (username,)).fetchone()
    conn.close()
    
    if user and verify_password(password, user['password_hash']):
        return dict(user)
    return None

def create_user(username, password, role):
    """Cria novo usuário."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        password_hash = hash_password(password)
        cursor.execute('''
            INSERT INTO users (username, password_hash, role) 
            VALUES (?, ?, ?)
        ''', (username, password_hash, role))
        conn.commit()
        return True, cursor.lastrowid
    except sqlite3.IntegrityError:
        return False, "Erro: Nome de usuário já existe."
    except sqlite3.Error as e:
        return False, f"Erro de banco de dados ao criar usuário: {e}"
    finally:
        conn.close()

def get_all_users():
    """Retorna todos os usuários."""
    conn = get_db_connection()
    users = conn.execute('SELECT id, username, role, active, created_at FROM users ORDER BY username').fetchall()
    conn.close()
    return users

def update_user(user_id, username=None, password=None, role=None, active=None):
    """Atualiza dados do usuário."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    updates = []
    params = []
    
    if username is not None:
        updates.append('username = ?')
        params.append(username)
    if password is not None and password.strip(): # Garante que não se atualize com senha vazia
        updates.append('password_hash = ?')
        params.append(hash_password(password))
    if role is not None:
        updates.append('role = ?')
        params.append(role)
    if active is not None:
        updates.append('active = ?')
        params.append(active)
    
    if not updates:
        return True, "Nenhuma alteração a ser feita."

    # Sempre adicionar sync_status quando houver atualizações
    updates.append('sync_status = CASE WHEN sync_status = \'pending_create\' THEN \'pending_create\' ELSE \'pending_update\' END')

    params.append(user_id)
    query = f'UPDATE users SET {", ".join(updates)} WHERE id = ?'
    
    try:
        cursor.execute(query, params)
        conn.commit()
        return True, "Usuário atualizado com sucesso."
    except sqlite3.IntegrityError:
        return False, "Erro: Nome de usuário já existe."
    except sqlite3.Error as e:
        return False, f"Erro de banco de dados ao atualizar usuário: {e}"
    finally:
        conn.close()

def log_user_session(user_id, action='login'):
    """Registra login/logout do usuário."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if action == 'login':
        cursor.execute('INSERT INTO user_sessions (user_id) VALUES (?)', (user_id,))
    elif action == 'logout':
        cursor.execute('''
            UPDATE user_sessions 
            SET logout_time = CURRENT_TIMESTAMP 
            WHERE user_id = ? AND logout_time IS NULL
        ''', (user_id,))
    
    conn.commit()
    conn.close()

def get_user_by_id(user_id):
    """Retorna dados do usuário pelo ID."""
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    conn.close()
    return dict(user) if user else None

def get_user_by_username(username: str):
    """Retorna dados do usuário pelo nome de usuário."""
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
    conn.close()
    return dict(user) if user else None

