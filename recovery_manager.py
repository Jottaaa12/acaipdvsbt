import os
import json
import logging
import shutil
from datetime import datetime, timedelta
from PyQt6.QtCore import QTimer, QThread, pyqtSignal, QObject, QMutex, QWaitCondition
from PyQt6.QtWidgets import QMessageBox, QApplication, QProgressDialog
import database as db
from typing import Optional, Dict, Any, List
import threading

class RecoveryManager(QObject):
    """
    Sistema de recuperação de dados para o PDV.
    Gerencia salvamento automático de sessão, recuperação de vendas não finalizadas
    e restauração de estado da aplicação.
    """

    # Sinais
    recovery_data_saved = pyqtSignal(str)    # tipo de dado salvo
    recovery_data_restored = pyqtSignal(str) # tipo de dado restaurado
    auto_save_performed = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.recovery_dir = "recovery"
        self.auto_save_interval = 30000  # 30 segundos
        self.max_recovery_files = 10

        # Estado da aplicação
        self.current_sale_data = {}
        self.current_session_state = {}
        self.last_sale_time = None

        # Mutex para thread safety
        self.mutex = QMutex()
        self.wait_condition = QWaitCondition()

        # Timer para auto-save
        self.auto_save_timer = QTimer()
        self.auto_save_timer.timeout.connect(self.perform_auto_save)

        # Estado
        self.is_auto_save_enabled = True
        self.is_saving = False

        # Criar diretório de recovery
        self._ensure_recovery_directory()

        # Carregar configurações
        self.load_settings()

    def _ensure_recovery_directory(self):
        """Garante que diretório de recovery existe."""
        try:
            if not os.path.exists(self.recovery_dir):
                os.makedirs(self.recovery_dir)
                logging.info(f"Diretório de recovery criado: {self.recovery_dir}")
        except Exception as e:
            logging.error(f"Erro ao criar diretório de recovery: {e}")

    def load_settings(self):
        """Carrega configurações do banco de dados."""
        try:
            interval = db.load_setting('recovery_auto_save_interval', '30000')
            self.auto_save_interval = int(interval)

            max_files = db.load_setting('recovery_max_files', '10')
            self.max_recovery_files = int(max_files)

            enabled = db.load_setting('recovery_auto_save_enabled', 'true')
            self.is_auto_save_enabled = enabled.lower() == 'true'

            logging.info(f"Configurações de recovery carregadas: intervalo={self.auto_save_interval}ms, max_files={self.max_recovery_files}")

        except Exception as e:
            logging.error(f"Erro ao carregar configurações de recovery: {e}")

    def save_settings(self):
        """Salva configurações no banco de dados."""
        try:
            db.save_setting('recovery_auto_save_interval', str(self.auto_save_interval))
            db.save_setting('recovery_max_files', str(self.max_recovery_files))
            db.save_setting('recovery_auto_save_enabled', 'true' if self.is_auto_save_enabled else 'false')
            logging.info("Configurações de recovery salvas")
        except Exception as e:
            logging.error(f"Erro ao salvar configurações de recovery: {e}")

    def start_auto_save(self):
        """Inicia salvamento automático."""
        if not self.is_auto_save_enabled:
            logging.info("Auto-save desabilitado")
            return

        self.auto_save_timer.start(self.auto_save_interval)
        logging.info(f"Auto-save iniciado (intervalo: {self.auto_save_interval}ms)")

    def stop_auto_save(self):
        """Para salvamento automático."""
        self.auto_save_timer.stop()
        logging.info("Auto-save parado")

    def save_sale_draft(self, sale_data: dict):
        """
        Salva rascunho da venda atual.

        Args:
            sale_data: Dados da venda em andamento
        """
        try:
            self.mutex.lock()

            self.current_sale_data = sale_data.copy()
            self.last_sale_time = datetime.now()

            # Salvar em arquivo
            self._save_sale_draft_to_file()

            # Salvar no banco também (para casos de crash)
            self._save_sale_draft_to_db()

            self.recovery_data_saved.emit("sale_draft")
            logging.info("Rascunho de venda salvo")

        except Exception as e:
            logging.error(f"Erro ao salvar rascunho de venda: {e}")
        finally:
            self.mutex.unlock()

    def _save_sale_draft_to_file(self):
        """Salva rascunho em arquivo."""
        try:
            filename = f"sale_draft_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            filepath = os.path.join(self.recovery_dir, filename)

            data = {
                'timestamp': datetime.now().isoformat(),
                'sale_data': self.current_sale_data,
                'version': '1.0'
            }

            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

        except Exception as e:
            logging.error(f"Erro ao salvar arquivo de rascunho: {e}")

    def _save_sale_draft_to_db(self):
        """Salva rascunho no banco de dados."""
        try:
            # Criar tabela se não existir
            conn = db.get_db_connection()
            cursor = conn.cursor()

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS recovery_sale_drafts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sale_data TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Salvar dados (simplificado)
            sale_json = json.dumps(self.current_sale_data, ensure_ascii=False)

            # Remover drafts antigos (manter apenas o mais recente)
            cursor.execute('DELETE FROM recovery_sale_drafts WHERE id NOT IN (SELECT id FROM recovery_sale_drafts ORDER BY created_at DESC LIMIT 1)')

            # Inserir novo draft
            cursor.execute('''
                INSERT OR REPLACE INTO recovery_sale_drafts (id, sale_data, updated_at)
                VALUES (1, ?, CURRENT_TIMESTAMP)
            ''', (sale_json,))

            conn.commit()
            conn.close()

        except Exception as e:
            logging.error(f"Erro ao salvar rascunho no banco: {e}")

    def recover_sale_draft(self) -> Optional[dict]:
        """
        Recupera venda não finalizada.

        Returns:
            dict: Dados da venda recuperada ou None se não houver
        """
        try:
            # Tentar recuperar do banco primeiro
            draft_data = self._recover_sale_draft_from_db()
            if draft_data:
                self.recovery_data_restored.emit("sale_draft_from_db")
                return draft_data

            # Tentar recuperar de arquivo
            draft_data = self._recover_sale_draft_from_file()
            if draft_data:
                self.recovery_data_restored.emit("sale_draft_from_file")
                return draft_data

            return None

        except Exception as e:
            logging.error(f"Erro ao recuperar rascunho de venda: {e}")
            return None

    def _recover_sale_draft_from_db(self) -> Optional[dict]:
        """Recupera rascunho do banco de dados."""
        try:
            conn = db.get_db_connection()
            cursor = conn.cursor()

            cursor.execute('SELECT sale_data FROM recovery_sale_drafts WHERE id = 1')
            row = cursor.fetchone()

            conn.close()

            if row:
                return json.loads(row['sale_data'])

        except Exception as e:
            logging.error(f"Erro ao recuperar rascunho do banco: {e}")

        return None

    def _recover_sale_draft_from_file(self) -> Optional[dict]:
        """Recupera rascunho do arquivo mais recente."""
        try:
            # Listar arquivos de rascunho
            draft_files = []
            for file in os.listdir(self.recovery_dir):
                if file.startswith('sale_draft_') and file.endswith('.json'):
                    filepath = os.path.join(self.recovery_dir, file)
                    mtime = os.path.getmtime(filepath)
                    draft_files.append((filepath, mtime))

            if not draft_files:
                return None

            # Pegar arquivo mais recente
            draft_files.sort(key=lambda x: x[1], reverse=True)
            latest_file = draft_files[0][0]

            # Carregar dados
            with open(latest_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            return data.get('sale_data')

        except Exception as e:
            logging.error(f"Erro ao recuperar rascunho de arquivo: {e}")

        return None

    def save_session_state(self):
        """
        Salva estado da sessão atual.
        Inclui configurações, estado da interface, etc.
        """
        try:
            self.mutex.lock()

            # Coletar estado atual da sessão
            session_state = {
                'timestamp': datetime.now().isoformat(),
                'current_user': getattr(self, 'current_user', None),
                'current_cash_session': getattr(self, 'current_cash_session', None),
                'ui_state': self._get_ui_state(),
                'settings': self._get_current_settings(),
                'version': '1.0'
            }

            self.current_session_state = session_state

            # Salvar em arquivo
            self._save_session_state_to_file()

            self.recovery_data_saved.emit("session_state")
            logging.info("Estado da sessão salvo")

        except Exception as e:
            logging.error(f"Erro ao salvar estado da sessão: {e}")
        finally:
            self.mutex.unlock()

    def _get_ui_state(self) -> dict:
        """Obtém estado atual da interface."""
        # Esta implementação seria expandida para capturar
        # estado específico da interface do usuário
        return {
            'current_page': 'sales',  # Exemplo
            'window_size': None,
            'preferences': {}
        }

    def _get_current_settings(self) -> dict:
        """Obtém configurações atuais."""
        try:
            return {
                'store_config': self._load_store_config(),
                'printer_config': self._load_printer_config(),
                'system_settings': self._load_system_settings()
            }
        except Exception as e:
            logging.error(f"Erro ao obter configurações: {e}")
            return {}

    def _load_store_config(self) -> dict:
        """Carrega configurações da loja."""
        try:
            config_path = os.path.join(os.getcwd(), 'config.json')
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    return json.load(f).get('store', {})
        except Exception:
            pass
        return {}

    def _load_printer_config(self) -> dict:
        """Carrega configurações da impressora."""
        try:
            config_path = os.path.join(os.getcwd(), 'config.json')
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    return json.load(f).get('printer', {})
        except Exception:
            pass
        return {}

    def _load_system_settings(self) -> dict:
        """Carrega configurações do sistema."""
        settings = {}
        try:
            setting_keys = [
                'backup_interval_hours',
                'backup_max_backups',
                'recovery_auto_save_interval',
                'whatsapp_notifications_enabled'
            ]

            for key in setting_keys:
                value = db.load_setting(key)
                if value is not None:
                    settings[key] = value

        except Exception as e:
            logging.error(f"Erro ao carregar configurações do sistema: {e}")

        return settings

    def _save_session_state_to_file(self):
        """Salva estado da sessão em arquivo."""
        try:
            filename = f"session_state_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            filepath = os.path.join(self.recovery_dir, filename)

            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(self.current_session_state, f, indent=2, ensure_ascii=False)

        except Exception as e:
            logging.error(f"Erro ao salvar arquivo de estado da sessão: {e}")

    def restore_session_state(self) -> bool:
        """
        Restaura estado da sessão anterior.

        Returns:
            bool: True se conseguiu restaurar
        """
        try:
            # Tentar restaurar do arquivo mais recente
            state_files = []
            for file in os.listdir(self.recovery_dir):
                if file.startswith('session_state_') and file.endswith('.json'):
                    filepath = os.path.join(self.recovery_dir, file)
                    mtime = os.path.getmtime(filepath)
                    state_files.append((filepath, mtime))

            if not state_files:
                logging.info("Nenhum estado de sessão encontrado para restauração")
                return False

            # Pegar arquivo mais recente
            state_files.sort(key=lambda x: x[1], reverse=True)
            latest_file = state_files[0][0]

            # Carregar dados
            with open(latest_file, 'r', encoding='utf-8') as f:
                state_data = json.load(f)

            # Aplicar restauração
            success = self._apply_session_state(state_data)

            if success:
                self.recovery_data_restored.emit("session_state")
                logging.info("Estado da sessão restaurado com sucesso")

            return success

        except Exception as e:
            logging.error(f"Erro ao restaurar estado da sessão: {e}")
            return False

    def _apply_session_state(self, state_data: dict) -> bool:
        """
        Aplica estado da sessão restaurado.

        Args:
            state_data: Dados do estado a restaurar

        Returns:
            bool: True se aplicado com sucesso
        """
        try:
            # Esta implementação seria expandida para aplicar
            # as configurações restauradas na aplicação

            # Por exemplo:
            # - Restaurar configurações da loja
            # - Restaurar configurações da impressora
            # - Aplicar configurações do sistema

            logging.info("Estado da sessão aplicado (simulado)")
            return True

        except Exception as e:
            logging.error(f"Erro ao aplicar estado da sessão: {e}")
            return False

    def perform_auto_save(self):
        """Executa salvamento automático."""
        if not self.is_auto_save_enabled or self.is_saving:
            return

        try:
            self.is_saving = True

            # Salvar estado da sessão
            self.save_session_state()

            # Se houver venda em andamento, salvar rascunho
            if self.current_sale_data:
                self.save_sale_draft(self.current_sale_data)

            self.auto_save_performed.emit()
            logging.debug("Auto-save executado")

        except Exception as e:
            logging.error(f"Erro no auto-save: {e}")
        finally:
            self.is_saving = False

    def cleanup_old_recovery_files(self):
        """Limpa arquivos antigos de recovery."""
        try:
            # Listar todos os arquivos de recovery
            all_files = []
            for file in os.listdir(self.recovery_dir):
                filepath = os.path.join(self.recovery_dir, file)
                mtime = os.path.getmtime(filepath)
                all_files.append((filepath, mtime))

            if len(all_files) <= self.max_recovery_files:
                return  # Nada para limpar

            # Ordenar por data (mais antigos primeiro)
            all_files.sort(key=lambda x: x[1])

            # Remover arquivos mais antigos
            files_to_remove = all_files[:-self.max_recovery_files]

            for filepath, _ in files_to_remove:
                try:
                    os.remove(filepath)
                    logging.info(f"Arquivo de recovery antigo removido: {os.path.basename(filepath)}")
                except Exception as e:
                    logging.error(f"Erro ao remover arquivo {filepath}: {e}")

            logging.info(f"Limpeza de recovery concluída: {len(files_to_remove)} arquivos removidos")

        except Exception as e:
            logging.error(f"Erro na limpeza de arquivos de recovery: {e}")

    def set_sale_data(self, sale_data: dict):
        """
        Define dados atuais da venda.

        Args:
            sale_data: Dados da venda em andamento
        """
        self.current_sale_data = sale_data

    def clear_sale_data(self):
        """Limpa dados da venda atual."""
        self.current_sale_data = {}
        self.last_sale_time = None

        # Remover rascunhos antigos
        try:
            conn = db.get_db_connection()
            cursor = conn.cursor()
            cursor.execute('DELETE FROM recovery_sale_drafts')
            conn.commit()
            conn.close()
        except Exception as e:
            logging.error(f"Erro ao limpar rascunhos do banco: {e}")

    def get_recovery_info(self) -> Dict[str, Any]:
        """
        Retorna informações sobre recovery.

        Returns:
            Dict com informações de recovery
        """
        try:
            # Contar arquivos de recovery
            recovery_files = 0
            total_size = 0

            for file in os.listdir(self.recovery_dir):
                filepath = os.path.join(self.recovery_dir, file)
                if os.path.isfile(filepath):
                    recovery_files += 1
                    total_size += os.path.getsize(filepath)

            return {
                'recovery_files_count': recovery_files,
                'total_size_mb': round(total_size / (1024 * 1024), 2),
                'auto_save_enabled': self.is_auto_save_enabled,
                'auto_save_interval_ms': self.auto_save_interval,
                'last_sale_time': self.last_sale_time,
                'has_sale_draft': bool(self.current_sale_data),
                'max_recovery_files': self.max_recovery_files
            }

        except Exception as e:
            logging.error(f"Erro ao obter informações de recovery: {e}")
            return {'error': str(e)}

    def set_auto_save_interval(self, interval_ms: int):
        """
        Define intervalo de auto-save.

        Args:
            interval_ms: Intervalo em milissegundos
        """
        if interval_ms < 5000:  # Mínimo 5 segundos
            raise ValueError("Intervalo mínimo é 5 segundos")

        self.auto_save_interval = interval_ms
        self.save_settings()
        self.restart_auto_save()

    def set_max_recovery_files(self, max_files: int):
        """
        Define número máximo de arquivos de recovery.

        Args:
            max_files: Número máximo de arquivos
        """
        if max_files < 1:
            raise ValueError("Deve manter pelo menos 1 arquivo")

        self.max_recovery_files = max_files
        self.save_settings()

    def enable_auto_save(self, enabled: bool = True):
        """Habilita/desabilita auto-save."""
        self.is_auto_save_enabled = enabled
        self.save_settings()

        if enabled:
            self.start_auto_save()
        else:
            self.stop_auto_save()

    def restart_auto_save(self):
        """Reinicia auto-save com novas configurações."""
        self.stop_auto_save()
        self.start_auto_save()

    def force_save_now(self):
        """Força salvamento imediato."""
        self.perform_auto_save()

# Instância global do RecoveryManager
recovery_manager = RecoveryManager()

# Funções de conveniência
def save_sale_draft(sale_data: dict):
    """Salva rascunho de venda."""
    recovery_manager.save_sale_draft(sale_data)

def recover_sale_draft() -> Optional[dict]:
    """Recupera rascunho de venda."""
    return recovery_manager.recover_sale_draft()

def save_session_state():
    """Salva estado da sessão."""
    recovery_manager.save_session_state()

def restore_session_state() -> bool:
    """Restaura estado da sessão."""
    return recovery_manager.restore_session_state()

def set_sale_data(sale_data: dict):
    """Define dados da venda atual."""
    recovery_manager.set_sale_data(sale_data)

def clear_sale_data():
    """Limpa dados da venda atual."""
    recovery_manager.clear_sale_data()

def get_recovery_info() -> Dict[str, Any]:
    """Obtém informações de recovery."""
    return recovery_manager.get_recovery_info()

def force_save_now():
    """Força salvamento imediato."""
    recovery_manager.force_save_now()
