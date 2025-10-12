import sqlite3
from .connection import get_db_connection

def save_setting(key, value):
    """Salva uma configuração no banco de dados."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT OR REPLACE INTO settings (key, value, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
        ''', (key, value))
        conn.commit()
        return True, "Configuração salva com sucesso."
    except sqlite3.Error as e:
        return False, f"Erro de banco de dados: {e}"
    finally:
        conn.close()

def load_setting(key, default=None):
    """Carrega uma configuração do banco de dados."""
    conn = get_db_connection()
    row = conn.execute('SELECT value FROM settings WHERE key = ?', (key,)).fetchone()
    conn.close()
    if row:
        return row['value']
    return default

def get_authorized_managers():
    """Busca a lista de números de telefone de gerentes autorizados a partir das configurações."""
    numbers_str = load_setting('whatsapp_manager_numbers', '')
    if not numbers_str:
        return []
    # Retorna uma lista de números, removendo espaços em branco
    return [num.strip() for num in numbers_str.split(',') if num.strip()]

def set_global_notification_status(enabled: bool):
    """Salva o status global das notificações (on/off)."""
    value_to_save = '1' if enabled else '0'
    return save_setting('whatsapp_notifications_globally_enabled', value_to_save)

def are_notifications_globally_enabled() -> bool:
    """Verifica se as notificações globais do WhatsApp estão ativadas."""
    status = load_setting('whatsapp_notifications_globally_enabled', '1') # Padrão é ativado
    return status == '1'
