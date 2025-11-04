import sqlite3
import logging
from .connection import get_db_connection

class SettingsRepository:
    def get_setting(self, key: str, default: str | None = None) -> str | None:
        """Busca o valor de uma configuração específica."""
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
            result = cursor.fetchone()
            conn.close()
            if result:
                return result['value']
            return default
        except sqlite3.Error as e:
            logging.error(f"Erro ao buscar configuração '{key}': {e}", exc_info=True)
            return default

    def save_setting(self, key: str, value: str):
        """Salva ou atualiza o valor de uma configuração específica."""
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            # O 'INSERT OR REPLACE' (baseado na constraint UNIQUE(key)) é perfeito aqui
            cursor.execute('''
                INSERT OR REPLACE INTO settings (key, value, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
            ''', (key, str(value)))
            conn.commit()
            conn.close()
            logging.info(f"Configuração '{key}' salva com valor '{value}'.")
        except sqlite3.Error as e:
            logging.error(f"Erro ao salvar configuração '{key}': {e}", exc_info=True)

    def get_authorized_managers(self):
        """Busca a lista de números de telefone de gerentes autorizados a partir das configurações."""
        numbers_str = self.get_setting('whatsapp_manager_numbers', '')
        if not numbers_str:
            return []
        # Retorna uma lista de números, removendo espaços em branco
        return [num.strip() for num in numbers_str.split(',') if num.strip()]

    def set_global_notification_status(self, enabled: bool):
        """Salva o status global das notificações (on/off)."""
        value_to_save = '1' if enabled else '0'
        self.save_setting('whatsapp_notifications_globally_enabled', value_to_save)

    def are_notifications_globally_enabled(self) -> bool:
        """Verifica se as notificações globais do WhatsApp estão ativadas."""
        status = self.get_setting('whatsapp_notifications_globally_enabled', '1') # Padrão é ativado
        return status == '1'

# --- Funções de fachada para manter a compatibilidade ---

_repo = SettingsRepository()

def get_setting(key: str, default: str | None = None) -> str | None:
    return _repo.get_setting(key, default)

def save_setting(key: str, value: str):
    return _repo.save_setting(key, value)

def get_authorized_managers():
    return _repo.get_authorized_managers()

def set_global_notification_status(enabled: bool):
    return _repo.set_global_notification_status(enabled)

def are_notifications_globally_enabled() -> bool:
    return _repo.are_notifications_globally_enabled()

# Alias para compatibilidade com código legado
load_setting = get_setting