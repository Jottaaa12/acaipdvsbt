
import sys
from PyQt6.QtCore import QObject, pyqtSignal, QThread, QTimer, pyqtSlot
from datetime import datetime, timedelta
import os
import json
import subprocess
import threading
import queue
import time
import shutil
import traceback
import hashlib
from typing import Dict, Any, Optional, List, Tuple

# Utilitário para caminho de dados persistentes
try:
    from utils import get_data_path
except Exception:
    def get_data_path(name: str) -> str:
        return os.path.join(os.getcwd(), name)

# Módulos WhatsApp customizados
from .whatsapp_logger import get_whatsapp_logger
from .whatsapp_config import get_whatsapp_config
from .whatsapp_command_handler import CommandHandler

# Renderização de QR via Python (sem browser)
try:
    import qrcode
except Exception:
    qrcode = None

class WhatsAppManager(QObject):
    """
    Integração WhatsApp robusta com sistema de retry, validações, cache e monitoring.
    """
    qr_code_ready = pyqtSignal(str)
    status_updated = pyqtSignal(str)
    error_occurred = pyqtSignal(str)
    log_updated = pyqtSignal(str)

    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        super().__init__()

        # Componentes principais
        self.logger = get_whatsapp_logger()
        self.config = get_whatsapp_config()

        # Estado da conexão
        self.is_ready = False
        self._worker_thread: Optional[WhatsAppWorker] = None
        self._session_lock = threading.RLock()  # Lock para sessão concorrente
        self._qr_timeout_timer: Optional[QTimer] = None

        # Cache e rate limiting
        self._phone_cache: Dict[str, Dict[str, Any]] = {}
        self._cache_lock = threading.RLock()  # Lock específico para operações de cache
        self._message_counts: Dict[str, List[datetime]] = {}  # Para rate limiting

        # Health monitoring
        self._health_timer: Optional[QTimer] = None
        self._last_health_check: Optional[datetime] = None
        self._connection_start_time: Optional[datetime] = None

        # Histórico de mensagens
        self._message_history: List[Dict[str, Any]] = []
        self._history_lock = threading.RLock()  # Lock específico para histórico

        # Carregar estado persistente
        self._load_persistent_cache()
        self._load_message_history()

        # Iniciar health monitoring se configurado
        if self.config.get('monitoring.enable_health_checks', True):
            self._start_health_monitoring()

        # Instanciar o handler de comandos (agora sem dependências)
        self.command_handler = CommandHandler()

    def connect(self, force_reconnect: bool = False) -> bool:
        """
        Inicia conexão com WhatsApp.

        Args:
            force_reconnect: Força reconexão mesmo se já estiver conectado

        Returns:
            bool: True se iniciou conexão, False se falhou
        """
        with self._session_lock:
            try:
                # Verificar se já está conectado
                if not force_reconnect and self._worker_thread and self._worker_thread.isRunning() and self.is_ready:
                    self.logger.log_connection("Já conectado, ignorando nova tentativa")
                    self.status_updated.emit("✅ Já está conectado!")
                    return True

                # Parar conexão existente se forçando reconexão
                if force_reconnect and self._worker_thread:
                    self.logger.log_connection("Forçando reconexão, parando worker atual")
                    self.disconnect()

                self.logger.log_connection("Iniciando conexão com WhatsApp", force_reconnect=force_reconnect)
                self.status_updated.emit("🔄 Iniciando conexão com WhatsApp...")

                # Criar e iniciar worker
                self._worker_thread = WhatsAppWorker(self)
                self._connection_start_time = datetime.now()

                # Conectar sinais do worker
                self._worker_thread.message_result.connect(self._on_message_result_received)

                self._worker_thread.start()

                return True

            except Exception as e:
                self.logger.log_error(f"Falha ao iniciar conexão: {e}",
                                    error_type='connection_init_failed',
                                    traceback=traceback.format_exc())
                self.error_occurred.emit(self.config.get_friendly_error_message('connection_failed'))
                return False

    def send_message(self, phone_number: str, message: str, bypass_cache: bool = False, message_type: str = 'normal') -> Dict[str, Any]:
        """
        Envia mensagem com validações robustas.

        Args:
            phone_number: Número do telefone
            message: Conteúdo da mensagem
            bypass_cache: Ignorar cache de validação

        Returns:
            dict: Resultado com status e informações da operação
        """
        result = {
            'success': False,
            'message_id': None,
            'error': None,
            'error_type': None
        }

        try:
            # Validação básica dos inputs
            validation_result = self._validate_message_inputs(phone_number, message)
            if not validation_result['valid']:
                result['error'] = validation_result['error']
                result['error_type'] = validation_result['error_type']
                self.logger.log_error(f"Validação falhou: {result['error']}", error_type=result['error_type'])
                self.error_occurred.emit(result['error'])
                return result

            phone_normalized = validation_result['normalized_phone']

            # Verificar rate limiting
            if self._is_rate_limited(phone_normalized, message_type):
                error_msg = self.config.get_friendly_error_message('rate_limited')
                result['error'] = error_msg
                result['error_type'] = 'rate_limited'
                self.logger.log_error(error_msg, error_type='rate_limited', phone=phone_normalized)
                self.error_occurred.emit(error_msg)
                return result

            # Verificar cache de números (se não for bypass)
            if not bypass_cache:
                cache_result = self._check_phone_cache(phone_normalized)
                if cache_result['action'] == 'block':
                    result['error'] = cache_result['error']
                    result['error_type'] = 'invalid_number'
                    self.error_occurred.emit(result['error'])
                    return result

            # Verificar se worker está disponível
            if not self._worker_thread or not self._worker_thread.isRunning():
                result['error'] = "Serviço WhatsApp não está em execução"
                result['error_type'] = 'worker_not_running'
                self.logger.log_error(result['error'], error_type='worker_not_running')
                self.error_occurred.emit(result['error'])
                return result

            # Enfileirar mensagem
            message_id = self._generate_message_id()
            self._worker_thread.enqueue_send(phone_normalized, message, message_id)

            # Registrar tentativa de envio
            self._record_message_attempt(message_id, phone_normalized, message)
            self._update_message_counts(phone_normalized)

            result['success'] = True
            result['message_id'] = message_id

            self.logger.log_message("Mensagem enfileirada com sucesso",
                                  message_id=message_id,
                                  phone_hash=hashlib.md5(phone_normalized.encode()).hexdigest(),
                                  message_length=len(message))

            return result

        except Exception as e:
            result['error'] = f"Erro interno ao enviar mensagem: {str(e)}"
            result['error_type'] = 'internal_error'
            self.logger.log_error(result['error'],
                                error_type='internal_error',
                                traceback=traceback.format_exc())
            self.error_occurred.emit(self.config.get_friendly_error_message('message_failed'))
            return result

    def disconnect(self, cleanup_session: bool = True) -> bool:
        """
        Desconecta WhatsApp gracefully.

        Args:
            cleanup_session: Remove diretório de sessão

        Returns:
            bool: True se desconectou com sucesso
        """
        with self._session_lock:
            try:
                self.logger.log_connection("Iniciando desconexão do WhatsApp")

                if self._worker_thread:
                    self._worker_thread.stop()
                    success = self._worker_thread.wait(10000)  # 10 segundos timeout

                    if success:
                        self.logger.log_connection("Worker parado com sucesso")
                    else:
                        self.logger.log_error("Timeout ao parar worker", error_type='worker_stop_timeout')
                        # Forçar terminação
                        self._force_worker_cleanup()

                    self._worker_thread = None

                # Cleanup opcional
                if cleanup_session:
                    self._cleanup_session_files()

                self.is_ready = False
                self._connection_start_time = None
                self.status_updated.emit("🔌 Desconectado")

                self.logger.log_connection("Desconexão concluída com sucesso")
                return True

            except Exception as e:
                self.logger.log_error(f"Falha na desconexão: {e}",
                                    error_type='disconnection_failed',
                                    traceback=traceback.format_exc())
                self.error_occurred.emit("Erro ao desconectar")
                return False

    def get_health_status(self) -> Dict[str, Any]:
        """Retorna status de saúde da integração WhatsApp."""
        return {
            'connected': self.is_ready,
            'worker_running': self._worker_thread and self._worker_thread.isRunning() if self._worker_thread else False,
            'connection_duration': (
                datetime.now() - self._connection_start_time
            ).total_seconds() if self._connection_start_time else 0,
            'cache_size': len(self._phone_cache),
            'message_history_count': len(self._message_history),
            'last_health_check': self._last_health_check.isoformat() if self._last_health_check else None,
        }

    def clear_cache(self) -> bool:
        """Limpa cache de números verificados."""
        try:
            self._phone_cache.clear()
            self._save_persistent_cache()
            self.logger.log_message("Cache de números limpo com sucesso")
            return True
        except Exception as e:
            self.logger.log_error(f"Falha ao limpar cache: {e}", error_type='cache_clear_failed')
            return False

    def get_message_history(self, limit: int = 100, phone_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retorna histórico de mensagens com filtros."""
        history = self._message_history

        if phone_filter:
            phone_normalized = self._normalize_phone(phone_filter)
            history = [msg for msg in history if msg.get('phone') == phone_normalized]

        return history[-limit:] if history else []

    def update_authorized_users(self):
        """Informa ao CommandHandler para recarregar a lista de usuários autorizados."""
        if self.command_handler:
            self.command_handler.update_authorized_managers()

    # Métodos privados de validação e cache
    def _validate_message_inputs(self, phone: str, message: str) -> Dict[str, Any]:
        """Valida inputs da mensagem."""
        result = {'valid': False, 'error': None, 'error_type': None, 'normalized_phone': None}

        # Validação de telefone
        phone_validation = self.config.validate_phone(phone)
        if not phone_validation['valid']:
            result['error'] = phone_validation['error'] or "Número de telefone inválido"
            result['error_type'] = 'invalid_phone'
            return result

        # Validação de mensagem
        if not message or not message.strip():
            result['error'] = "Mensagem não pode estar vazia"
            result['error_type'] = 'empty_message'
            return result

        max_length = self.config.get('messages.max_message_length', 4096)
        if len(message) > max_length:
            result['error'] = f"Mensagem muito longa (máx. {max_length} caracteres)"
            result['error_type'] = 'message_too_long'
            return result

        result['valid'] = True
        result['normalized_phone'] = phone_validation['normalized']
        return result

    def _is_rate_limited(self, phone: str, message_type: str = 'normal') -> bool:
        """Verifica se número está rate limited baseado no tipo de mensagem."""
        if not self.config.get('rate_limiting.enable_rate_limiting', True):
            return False

        now = datetime.now()
        phone_key = f"{phone}_{message_type}"
        phone_counts = self._message_counts.get(phone_key, [])

        # Limpar mensagens antigas (última hora)
        cutoff_time = now - timedelta(hours=1)
        phone_counts = [t for t in phone_counts if t > cutoff_time]
        self._message_counts[phone_key] = phone_counts

        # Definir limites baseados no tipo de mensagem
        if message_type == 'system_automatic':
            # Limites mais permissivos para mensagens automáticas do sistema
            max_per_hour = self.config.get('rate_limiting.max_system_messages_per_hour', 50)
            max_per_minute = self.config.get('rate_limiting.max_system_messages_per_minute', 5)
            burst_limit = self.config.get('rate_limiting.system_burst_limit', 3)
        else:
            # Limites mais restritivos para mensagens manuais
            max_per_hour = self.config.get('rate_limiting.max_messages_per_hour', 100)
            max_per_minute = self.config.get('rate_limiting.max_messages_per_minute', 10)
            burst_limit = self.config.get('rate_limiting.burst_limit', 5)

        # Verificar limite por hora
        if len(phone_counts) >= max_per_hour:
            return True

        # Verificar limite por minuto (últimas mensagens)
        recent_cutoff = now - timedelta(minutes=1)
        recent_count = len([t for t in phone_counts if t > recent_cutoff])

        if recent_count >= max_per_minute:
            return True

        # Verificar burst limit (últimos 10 segundos)
        burst_cutoff = now - timedelta(seconds=10)
        burst_count = len([t for t in phone_counts if t > burst_cutoff])

        if burst_count >= burst_limit:
            return True

        return False

    def _check_phone_cache(self, phone: str) -> Dict[str, Any]:
        """Verifica número no cache."""
        with self._cache_lock:
            cache_entry = self._phone_cache.get(phone)
            if not cache_entry:
                return {'action': 'verify', 'error': None}

            # Verificar TTL
            ttl_hours = self.config.get('validation.phone_verification_ttl_hours', 24)
            if datetime.now() - cache_entry['timestamp'] > timedelta(hours=ttl_hours):
                del self._phone_cache[phone]
                self._save_persistent_cache()
                return {'action': 'verify', 'error': None}

            # Retornar resultado do cache
            if not cache_entry['exists']:
                return {'action': 'block', 'error': 'Número não existe no WhatsApp'}

            return {'action': 'allow', 'error': None}

    def _update_phone_cache(self, phone: str, exists: bool):
        """Atualiza cache de números."""
        with self._cache_lock:
            self._phone_cache[phone] = {
                'exists': exists,
                'timestamp': datetime.now()
            }
            self._save_persistent_cache()

    def _record_message_attempt(self, message_id: str, phone: str, message: str):
        """Registra tentativa de envio no histórico."""
        history_entry = {
            'id': message_id,
            'phone': phone,
            'message': message,
            'timestamp': datetime.now().isoformat(),
            'status': 'sent'  # será atualizado pelo worker
        }

        self._message_history.append(history_entry)

        # Manter limite no histórico
        max_entries = self.config.get('monitoring.max_history_entries', 10000)
        if len(self._message_history) > max_entries:
            self._message_history = self._message_history[-max_entries:]

        self._save_message_history()

    def _record_message_result(self, message_id: str, success: bool, error: Optional[str] = None):
        """Atualiza resultado da mensagem no histórico."""
        for msg in reversed(self._message_history):
            if msg['id'] == message_id:
                msg['status'] = 'delivered' if success else 'failed'
                if error:
                    msg['error'] = error
                msg['delivered_at'] = datetime.now().isoformat()
                self._save_message_history()
                break

    # Métodos de persistência
    def _load_persistent_cache(self):
        """Carrega cache persistente."""
        try:
            cache_file = self.config.get_path('cache_file')
            if os.path.exists(cache_file):
                with open(cache_file, 'r', encoding='utf-8') as f:
                    cached_data = json.load(f)
                    # Converter timestamps de volta para datetime
                    for phone, data in cached_data.items():
                        data['timestamp'] = datetime.fromisoformat(data['timestamp'])
                    self._phone_cache = cached_data
        except Exception as e:
            self.logger.log_error(f"Falha ao carregar cache: {e}", error_type='cache_load_failed')

    def _save_persistent_cache(self):
        """Salva cache persistente."""
        try:
            cache_file = self.config.get_path('cache_file')
            # Converter datetimes para strings
            save_data = {}
            for phone, data in self._phone_cache.items():
                save_data[phone] = data.copy()
                save_data[phone]['timestamp'] = data['timestamp'].isoformat()

            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(save_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            self.logger.log_error(f"Falha ao salvar cache: {e}", error_type='cache_save_failed')

    def _load_message_history(self):
        """Carrega histórico de mensagens."""
        try:
            history_file = self.config.get_path('history_file')
            if os.path.exists(history_file):
                with open(history_file, 'r', encoding='utf-8') as f:
                    self._message_history = json.load(f)
        except Exception as e:
            self.logger.log_error(f"Falha ao carregar histórico: {e}", error_type='history_load_failed')

    def _save_message_history(self):
        """Salva histórico de mensagens."""
        try:
            history_file = self.config.get_path('history_file')
            with open(history_file, 'w', encoding='utf-8') as f:
                json.dump(self._message_history, f, indent=2, ensure_ascii=False)
        except Exception as e:
            self.logger.log_error(f"Falha ao salvar histórico: {e}", error_type='history_save_failed')

    # Métodos utilitários
    def _generate_message_id(self) -> str:
        """Gera ID único para mensagem."""
        return hashlib.md5(f"{datetime.now().isoformat()}{id(self)}".encode()).hexdigest()

    def _normalize_phone(self, phone: str) -> Optional[str]:
        """Normaliza número de telefone para comparação."""
        validation = self.config.validate_phone(phone)
        return validation['normalized'] if validation['valid'] else None

    def _update_message_counts(self, phone: str):
        """Atualiza contadores de mensagens para rate limiting."""
        if phone not in self._message_counts:
            self._message_counts[phone] = []
        self._message_counts[phone].append(datetime.now())

        # Limpar contadores antigos
        cutoff = datetime.now() - timedelta(hours=1)
        self._message_counts[phone] = [t for t in self._message_counts[phone] if t > cutoff]

    def _cleanup_session_files(self):
        """Remove arquivos da sessão."""
        try:
            session_dir = self.config.get_path('session_dir')
            if os.path.exists(session_dir):
                shutil.rmtree(session_dir)
                self.logger.log_connection("Arquivos de sessão removidos")
        except Exception as e:
            self.logger.log_error(f"Erro ao limpar sessão: {e}", error_type='session_cleanup_failed')

    def _force_worker_cleanup(self):
        """Força limpeza do worker travado."""
        try:
            if self._worker_thread and hasattr(self._worker_thread, 'process'):
                process = self._worker_thread.process
                if process and process.poll() is None:
                    self.logger.log_error("Forçando terminação do processo worker", error_type='force_cleanup')
                    process.terminate()
                    time.sleep(0.5)
                    if process.poll() is None:
                        process.kill()
        except Exception as e:
            self.logger.log_error(f"Erro no cleanup forçado: {e}", error_type='force_cleanup_failed')

    def _start_health_monitoring(self):
        """Inicia monitoramento de saúde."""
        self._health_timer = QTimer(self)
        self._health_timer.timeout.connect(self._perform_health_check)
        interval_ms = int(self.config.get('connection.health_check_interval', 60.0) * 1000)
        self._health_timer.start(interval_ms)

    @pyqtSlot()
    def _perform_health_check(self):
        """Realiza verificação de saúde."""
        try:
            status = self.get_health_status()
            self._last_health_check = datetime.now()

            self.logger.log_health_check(f"Status: {status['connected']}", **status)

            # Emitir alertas se necessário
            if status['worker_running'] and not status['connected']:
                self.logger.log_error("Worker rodando mas não conectado", error_type='health_worker_disconnected')
                # Poderia emitir sinal de alerta aqui

        except Exception as e:
            self.logger.log_error(f"Falha no health check: {e}", error_type='health_check_failed')

    @pyqtSlot(str, bool, str)
    def _on_message_result_received(self, message_id: str, success: bool, error: str):
        """Processa resultado de envio de mensagem do worker."""
        try:
            self._record_message_result(message_id, success, error)

            # Emitir log de auditoria
            if success:
                self.logger.log_audit("message_sent", "", "", True,
                                    message_id=message_id, success=True)
            else:
                self.logger.log_audit("message_failed", "", "", False,
                                    message_id=message_id, error=error, success=False)

        except Exception as e:
            self.logger.log_error(f"Erro ao processar resultado da mensagem: {e}",
                                error_type='message_result_processing_error',
                                message_id=message_id)

class WhatsAppWorker(QThread):
    """
    Worker thread robusto para WhatsApp com sistema de retry e validações.
    """

    # Sinais para comunicação com manager
    connection_retry = pyqtSignal(int)  # retry_count
    connection_failed_permanently = pyqtSignal()
    message_result = pyqtSignal(str, bool, str)  # message_id, success, error

    def __init__(self, manager: WhatsAppManager):
        super().__init__()
        self.manager = manager

        # Controle de execução
        self._running = threading.Event()
        self._running.set()
        self._shutdown_event = threading.Event()

        # Filas thread-safe
        self._send_queue: "queue.Queue[Dict[str, Any]]" = queue.Queue()
        self._retry_queue: "queue.Queue[Dict[str, Any]]" = queue.Queue()

        # Componentes
        self.logger = manager.logger
        self.config = manager.config

        # Processo Node.js
        self.process: subprocess.Popen | None = None
        self._process_lock = threading.RLock()

        # Estado da conexão
        self._connection_attempts = 0
        self._last_connection_attempt: Optional[datetime] = None
        self._reconnect_timer: Optional[QTimer] = None

        # Cache de validação (compartilhado com manager)
        self._phone_validation_cache: Dict[str, Dict[str, Any]] = {}

        # Estatísticas
        self._messages_sent = 0
        self._messages_failed = 0

        # Caminhos
        self.project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        self.session_path = self.config.get_path('session_dir')
        self.qr_image_path = self.config.get_path('session_dir') + '_qr.png'
        self.bridge_path = os.path.join(self.project_root, "wa_bridge.js")

        # Garantir que diretórios existam
        os.makedirs(os.path.dirname(self.session_path), exist_ok=True)

    def run(self):
        """Loop principal do worker com sistema de retry robusto."""
        self.logger.log_connection("Worker WhatsApp iniciado")

        try:
            while self._running.is_set():
                try:
                    # Iniciar/processar conexão
                    if self._start_connection_with_retry():
                        # Conexão estabelecida, iniciar processamento
                        self._process_connection_loop()
                    else:
                        # Falha permanente, sair
                        self.logger.log_connection("Falha permanente na conexão, encerrando worker")
                        break

                except Exception as e:
                    self.logger.log_error(f"Erro no loop principal do worker: {e}",
                                        error_type='worker_main_loop_error',
                                        traceback=traceback.format_exc())

                    # Aguardar antes de tentar novamente
                    if self._running.is_set():
                        retry_delay = self.config.get_backoff_delay(min(self._connection_attempts, 5))
                        self.logger.log_connection(f"Aguardando {retry_delay:.1f}s antes de retentar")
                        time.sleep(retry_delay)
                    else:
                        break

        except Exception as e:
            self.logger.log_error(f"Erro fatal no worker: {e}",
                                error_type='worker_fatal_error',
                                traceback=traceback.format_exc())
        finally:
            self._cleanup_worker()
            self.logger.log_connection("Worker WhatsApp finalizado")

    def stop(self):
        """Para o worker de forma graceful."""
        self.logger.log_connection("Solicitando parada do worker")
        self._running.clear()
        self._shutdown_event.set()

        # Tentar shutdown graceful do processo
        if self.process:
            try:
                self._write_stdin_json({"action": "shutdown"})
            except Exception as e:
                self.logger.log_error(f"Erro ao enviar shutdown: {e}", error_type='shutdown_send_error')

    def enqueue_send(self, phone: str, message: str, message_id: Optional[str] = None):
        """Enfileira mensagem para envio."""
        payload = {
            "action": "send",
            "phone": phone,
            "message": message,
            "message_id": message_id or self._generate_message_id(),
            "timestamp": datetime.now().isoformat(),
            "retry_count": 0
        }
        self._send_queue.put(payload)
        self.logger.log_message("Mensagem enfileirada no worker",
                              message_id=payload['message_id'],
                              queue_size=self._send_queue.qsize())

    def _start_connection_with_retry(self) -> bool:
        """Inicia conexão com sistema de retry e backoff."""
        max_attempts = self.config.get('connection.max_reconnect_attempts', 10)

        while self._running.is_set() and self._connection_attempts < max_attempts:
            self._connection_attempts += 1
            self._last_connection_attempt = datetime.now()

            self.logger.log_connection(f"Tentativa de conexão {self._connection_attempts}/{max_attempts}")
            self.connection_retry.emit(self._connection_attempts)

            try:
                if self._establish_connection():
                    self.logger.log_connection("Conexão estabelecida com sucesso")
                    self._connection_attempts = 0  # Reset contador
                    return True

            except Exception as e:
                self.logger.log_error(f"Falha na conexão (tentativa {self._connection_attempts}): {e}",
                                    error_type='connection_attempt_failed',
                                    attempt=self._connection_attempts)

            # Calcular delay de backoff
            if self._connection_attempts < max_attempts:
                delay = self.config.get_backoff_delay(self._connection_attempts)
                self.logger.log_connection(f"Aguardando {delay:.1f}s antes da próxima tentativa")

                # Aguardar com possibilidade de interrupção
                interrupted = self._shutdown_event.wait(delay)
                if interrupted:
                    break

        # Falha permanente
        self.connection_failed_permanently.emit()
        self.logger.log_error(f"Falha permanente após {max_attempts} tentativas",
                            error_type='connection_permanent_failure')
        return False

    def _establish_connection(self) -> bool:
        """Estabelece conexão Node.js."""
        try:
            # Verificar Node.js
            node_cmd = self._find_node_command()
            if not node_cmd:
                raise RuntimeError("Node.js não encontrado")

            # Iniciar processo
            with self._process_lock:
                args = [node_cmd, self.bridge_path, self.session_path]

                self.process = subprocess.Popen(
                    args,
                    cwd=self.project_root,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    bufsize=1,
                    encoding='utf-8',
                    creationflags=(subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0),
                )

            # Iniciar threads de comunicação
            threading.Thread(target=self._read_stdout, daemon=True, name='stdout_reader').start()
            threading.Thread(target=self._read_stderr, daemon=True, name='stderr_reader').start()
            threading.Thread(target=self._sender_loop, daemon=True, name='sender_loop').start()

            # Aguardar indicação de que processo iniciou
            timeout = self.config.get('connection.connection_timeout', 30.0)
            start_time = time.time()

            while time.time() - start_time < timeout and self._running.is_set():
                with self._process_lock:
                    if self.process and self.process.poll() is not None:
                        # Processo terminou, verificar se foi erro
                        rc = self.process.returncode
                        if rc != 0:
                            stdout, stderr = self.process.communicate()
                            raise RuntimeError(f"Processo Node.js falhou (código {rc}): {stderr}")
                        break
                time.sleep(0.1)

            return self._running.is_set()

        except Exception as e:
            self._cleanup_process()
            raise

    def _process_connection_loop(self):
        """Loop de processamento enquanto conectado."""
        self.logger.log_connection("Entrando no loop de processamento")

        while self._running.is_set():
            try:
                if self.process and self.process.poll() is not None:
                    # Processo terminou
                    rc = self.process.returncode
                    self.logger.log_error(f"Processo Node.js terminou com código {rc}",
                                        error_type='process_terminated',
                                        return_code=rc)
                    break

                # Processar mensagens pendentes
                self._process_pending_messages()

                time.sleep(0.1)

            except Exception as e:
                self.logger.log_error(f"Erro no loop de processamento: {e}",
                                    error_type='processing_loop_error',
                                    traceback=traceback.format_exc())
                break

    def _process_pending_messages(self):
        """Processa mensagens na fila de envio."""
        try:
            while not self._send_queue.empty() and self._running.is_set():
                payload = self._send_queue.get_nowait()
                self._send_message_to_bridge(payload)
                self._send_queue.task_done()
        except queue.Empty:
            pass

    def _send_message_to_bridge(self, payload: Dict[str, Any]):
        """Envia mensagem para o bridge Node.js."""
        try:
            self._write_stdin_json(payload)
            self.logger.log_message("Mensagem enviada para bridge",
                                  message_id=payload.get('message_id'),
                                  retry_count=payload.get('retry_count', 0))

        except Exception as e:
            self.logger.log_error(f"Falha ao enviar mensagem para bridge: {e}",
                                error_type='bridge_send_failed',
                                message_id=payload.get('message_id'))

            # Re-enfileirar para retry se apropriado
            if payload.get('retry_count', 0) < 3:
                payload['retry_count'] = payload.get('retry_count', 0) + 1
                self._retry_queue.put(payload)

    def _sender_loop(self):
        """Loop para envio de mensagens para o bridge."""
        while self._running.is_set():
            try:
                # Processar mensagens normais
                try:
                    payload = self._send_queue.get(timeout=0.5)
                    self._send_message_to_bridge(payload)
                except queue.Empty:
                    pass

                # Processar retries
                try:
                    retry_payload = self._retry_queue.get_nowait()
                    # Aguardar antes de retry
                    time.sleep(1.0)
                    self._send_message_to_bridge(retry_payload)
                except queue.Empty:
                    pass

            except Exception as e:
                self.logger.log_error(f"Erro no loop de envio: {e}",
                                    error_type='sender_loop_error',
                                    traceback=traceback.format_exc())
                time.sleep(1.0)  # Evitar loop apertado em caso de erro

    def _write_stdin_json(self, obj: Dict[str, Any]):
        """Escreve dados JSON no stdin do processo."""
        with self._process_lock:
            if self.process and self.process.stdin:
                try:
                    line = json.dumps(obj, ensure_ascii=False, default=str)
                    self.process.stdin.write(line + "\n")
                    self.process.stdin.flush()
                except (BrokenPipeError, OSError) as e:
                    self.logger.log_error(f"Erro de comunicação com processo: {e}",
                                        error_type='stdin_write_error')
                    raise
            else:
                raise RuntimeError("Processo não disponível para escrita")

    def _read_stdout(self):
        """Lê saída padrão do processo Node.js."""
        try:
            with self._process_lock:
                if not self.process or not self.process.stdout:
                    return

            for raw in self.process.stdout:
                if not self._running.is_set():
                    break

                line = raw.strip()
                if not line:
                    continue

                try:
                    msg = json.loads(line)
                    self._handle_bridge_message(msg)
                except json.JSONDecodeError as e:
                    self.logger.log_error(f"Linha inválida do bridge: {line}",
                                        error_type='bridge_json_error',
                                        raw_line=raw)

        except Exception as e:
            self.logger.log_error(f"Erro na leitura stdout: {e}", error_type='stdout_read_error')

    def _read_stderr(self):
        """Lê saída de erro do processo Node.js."""
        try:
            with self._process_lock:
                if not self.process or not self.process.stderr:
                    return

            for raw in self.process.stderr:
                if not self._running.is_set():
                    break

                line = raw.strip()
                if line:
                    self.logger.log_error(f"Bridge stderr: {line}",
                                        error_type='bridge_stderr',
                                        stderr_line=line)

        except Exception as e:
            self.logger.log_error(f"Erro na leitura stderr: {e}", error_type='stderr_read_error')

    def _handle_bridge_message(self, msg: Dict[str, Any]):
        """Processa mensagens recebidas do bridge."""
        try:
            msg_type = msg.get("type")

            if msg_type == "status":
                self._handle_status_message(msg)
            elif msg_type == "qr":
                self._handle_qr_message(msg)
            elif msg_type == "error":
                self._handle_error_message(msg)
            elif msg_type == "log":
                self._handle_log_message(msg)
            elif msg_type == "message_result":
                self._handle_message_result(msg)
            elif msg_type == "message":
                message_data = msg.get("data", {})
                if message_data:
                    # A função process_command retorna uma LISTA de tuplas (response, recipient)
                    responses = self.manager.command_handler.process_command(message_data, self.manager)
                    if responses:
                        for response, recipient in responses:
                            if response and recipient:
                                self.manager.send_message(recipient, response, message_type='command_response')
            elif msg_type == "incoming_command": # Manter compatibilidade se houver outro uso
                responses = self.manager.command_handler.process_command(msg.get("data", {}), self.manager)
                if responses:
                    for response, recipient in responses:
                        if response and recipient:
                            self.manager.send_message(recipient, response, message_type='command_response')

        except Exception as e:
            self.logger.log_error(f"Erro ao processar mensagem do bridge: {e}",
                                error_type='bridge_message_processing_error',
                                message=msg)

    def _handle_status_message(self, msg: Dict[str, Any]):
        """Processa mensagens de status."""
        status = msg.get("data", "")
        self.logger.log_connection(f"Status do bridge: {status}")

        if status == "connected":
            self.manager.is_ready = True
            self.manager.status_updated.emit("✅ Conectado com sucesso!")
        elif status.startswith("Erro") or "falhou" in status.lower():
            self.manager.error_occurred.emit(status)
        else:
            self.manager.status_updated.emit(status)

    def _handle_qr_message(self, msg: Dict[str, Any]):
        """Processa mensagens QR code."""
        # Ignorar novos QRs se já estivermos conectados.
        # A biblioteca pode enviar QRs de atualização periodicamente.
        if self.manager.is_ready:
            self.logger.log_connection("QR code de atualização recebido, ignorando.")
            return

        qr_text = msg.get("data", "")
        try:
            if qrcode is None:
                raise RuntimeError("Biblioteca qrcode não disponível")

            img = qrcode.make(qr_text)
            img.save(self.qr_image_path)
            self.manager.qr_code_ready.emit(self.qr_image_path)
            self.manager.status_updated.emit("ℹ️ QR Code gerado - escaneie com WhatsApp")

            # Iniciar timeout do QR se configurado
            qr_timeout = self.config.get('ui.qr_code_timeout', 300)
            if qr_timeout > 0:
                self._start_qr_timeout(qr_timeout)

        except Exception as e:
            self.logger.log_error(f"Falha ao gerar QR code: {e}", error_type='qr_generation_failed')
            self.manager.error_occurred.emit("❌ Falha ao gerar QR Code")

    def _handle_error_message(self, msg: Dict[str, Any]):
        """Processa mensagens de erro."""
        error_msg = str(msg.get("data", "Erro desconhecido"))
        self.logger.log_error(f"Erro do bridge: {error_msg}", error_type='bridge_error')
        self.manager.error_occurred.emit(error_msg)

    def _handle_log_message(self, msg: Dict[str, Any]):
        """Processa mensagens de log."""
        log_msg = str(msg.get("data", ""))
        self.logger.log_message(f"Bridge log: {log_msg}")
        self.manager.log_updated.emit(log_msg)

    def _handle_message_result(self, msg: Dict[str, Any]):
        """Processa resultados de envio de mensagens."""
        message_id = msg.get('message_id')
        success = msg.get('success', False)
        error = msg.get('error')

        if success:
            self._messages_sent += 1
            self.logger.log_message("Mensagem entregue",
                                  message_id=message_id,
                                  total_sent=self._messages_sent)
        else:
            self._messages_failed += 1
            self.logger.log_error(f"Falha no envio: {error}",
                                error_type='message_send_failed',
                                message_id=message_id,
                                total_failed=self._messages_failed)

        # Atualizar cache de validação se aplicável
        if msg.get('phone_validation_attempted'):
            phone = msg.get('phone')
            exists = msg.get('phone_exists', False)
            self.manager._update_phone_cache(phone, exists)

        # Notificar manager
        self.message_result.emit(message_id, success, error or "")
        self.manager._record_message_result(message_id, success, error)

    def _cleanup_worker(self):
        """Limpa recursos do worker."""
        self.logger.log_connection("Iniciando cleanup do worker")

        try:
            self._cleanup_process()
            self._send_queue = queue.Queue()  # Limpar filas
            self._retry_queue = queue.Queue()
        except Exception as e:
            self.logger.log_error(f"Erro no cleanup: {e}", error_type='worker_cleanup_error')

    def _cleanup_process(self):
        """Finaliza processo Node.js."""
        with self._process_lock:
            if self.process:
                try:
                    if self.process.poll() is None:
                        # Processo ainda rodando, tentar shutdown graceful
                        try:
                            self._write_stdin_json({"action": "shutdown"})
                            self.process.wait(timeout=5.0)
                        except subprocess.TimeoutExpired:
                            # Timeout, forçar kill
                            self.process.kill()
                            self.process.wait(timeout=2.0)
                except Exception as e:
                    self.logger.log_error(f"Erro ao finalizar processo: {e}",
                                        error_type='process_cleanup_error')
                finally:
                    self.process = None

    def _start_qr_timeout(self, timeout_seconds: int):
        """Inicia timeout para QR code."""
        if self._reconnect_timer:
            self._reconnect_timer.stop()

        self._reconnect_timer = QTimer()
        self._reconnect_timer.setSingleShot(True)
        self._reconnect_timer.timeout.connect(self._on_qr_timeout)
        self._reconnect_timer.start(timeout_seconds * 1000)

    @pyqtSlot()
    def _on_qr_timeout(self):
        """Callback quando QR code expira."""
        self.logger.log_connection("QR Code expirou")
        self.manager.error_occurred.emit("QR Code expirou. Gere um novo QR Code.")

    def _find_node_command(self) -> Optional[str]:
        """Localiza comando Node.js."""
        # Primeiro tentar PATH
        path_cmd = shutil.which("node") or shutil.which("node.exe")
        if path_cmd:
            return path_cmd

        # Tentar caminhos comuns no Windows
        common_paths = [
            "C:\\Program Files\\nodejs\\node.exe",
            "C:\\Program Files (x86)\\nodejs\\node.exe",
            os.path.expandvars("%LOCALAPPDATA%\\nvm\\current\\node.exe"),
        ]

        for path in common_paths:
            if os.path.exists(path):
                return path

        return None

    def _generate_message_id(self) -> str:
        """Gera ID único para mensagem."""
        return hashlib.md5(f"{datetime.now().isoformat()}{threading.current_thread().ident}".encode()).hexdigest()

