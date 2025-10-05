from PyQt6.QtCore import QObject, pyqtSignal, QRunnable, QThreadPool, QTimer
import traceback
import logging
import time
from typing import Optional, Callable, Any, Dict
from datetime import datetime

class WorkerSignals(QObject):
    """
    Sinais aprimorados para worker threads.

    Sinais suportados:
    - started: Quando a thread inicia
    - progress: Progresso da operação (valor, mensagem)
    - finished: Quando termina com sucesso
    - error: Quando ocorre erro (erro, traceback)
    - cancelled: Quando é cancelada
    """

    started = pyqtSignal()
    progress = pyqtSignal(int, str)  # progresso (0-100), mensagem
    finished = pyqtSignal(object)   # resultado da operação
    error = pyqtSignal(tuple)       # (erro, traceback)
    cancelled = pyqtSignal()

class EnhancedWorker(QRunnable):
    """
    Worker thread aprimorado com suporte a progresso, cancelamento e melhor tratamento de erros.

    :param callback: Função a ser executada na thread
    :param args: Argumentos posicionais para a função
    :param kwargs: Argumentos nomeados para a função
    """

    def __init__(self, fn: Callable, *args, **kwargs):
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()

        # Controle de execução
        self.is_cancelled = False
        self.start_time = None
        self.execution_id = id(self)

    def run(self):
        """Executa a função na thread."""
        self.start_time = time.time()

        try:
            # Emitir sinal de início
            self.signals.started.emit()

            # Executar função
            result = self.fn(*self.args, **self.kwargs)

            # Verificar se foi cancelada durante execução
            if self.is_cancelled:
                self.signals.cancelled.emit()
                return

            # Emitir resultado
            self.signals.finished.emit(result)

        except Exception as e:
            # Emitir erro com traceback completo
            error_info = (e, traceback.format_exc())
            self.signals.error.emit(error_info)
            logging.error(f"Erro na thread {self.execution_id}: {e}", exc_info=True)
        finally:
            # Log de execução
            execution_time = time.time() - self.start_time
            logging.info(f"Thread {self.execution_id} finalizada em {execution_time:.2f}s")

    def cancel(self):
        """Cancela execução da thread."""
        self.is_cancelled = True
        logging.info(f"Thread {self.execution_id} cancelada")

    def update_progress(self, value: int, message: str = ""):
        """Atualiza progresso (deve ser chamado pela função em execução)."""
        if not self.is_cancelled:
            self.signals.progress.emit(value, message)

class WorkerProgressCallback:
    """Callback helper para facilitar atualização de progresso."""

    def __init__(self, worker: EnhancedWorker):
        self.worker = worker

    def __call__(self, progress: int, message: str = ""):
        """Atualiza progresso."""
        self.worker.update_progress(progress, message)

class Worker(QRunnable):
    """
    Worker thread básico (mantido para compatibilidade).

    Para novas implementações, use EnhancedWorker.
    """

    def __init__(self, fn, *args, **kwargs):
        super(Worker, self).__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()

    def run(self):
        """Executa a função."""
        try:
            result = self.fn(*self.args, **self.kwargs)
        except Exception as e:
            self.signals.error.emit((e, traceback.format_exc()))
        else:
            self.signals.finished.emit(result)
        finally:
            pass

class ThreadManager(QObject):
    """
    Gerenciador centralizado de threads para o PDV.
    Controla pool de threads, fila de execução e monitoramento.
    """

    # Sinais globais
    thread_started = pyqtSignal(str)    # nome da operação
    thread_finished = pyqtSignal(str)   # nome da operação
    thread_error = pyqtSignal(str, str) # nome da operação, erro
    all_threads_finished = pyqtSignal()

    def __init__(self, max_workers: int = 4):
        super().__init__()
        self.thread_pool = QThreadPool.globalInstance()
        self.thread_pool.setMaxThreadCount(max_workers)

        # Controle de threads ativas
        self.active_threads: Dict[str, EnhancedWorker] = {}
        self.thread_operations: Dict[str, Dict[str, Any]] = {}

        # Timer para monitoramento
        self.monitor_timer = QTimer()
        self.monitor_timer.timeout.connect(self._monitor_threads)
        self.monitor_timer.start(1000)  # Monitorar a cada segundo

        logging.info(f"ThreadManager iniciado com {max_workers} workers")

    def start_worker(self, name: str, fn: Callable, *args,
                    progress_callback: bool = False, **kwargs) -> str:
        """
        Inicia uma nova worker thread.

        Args:
            name: Nome identificador da operação
            fn: Função a ser executada
            progress_callback: Se deve incluir callback de progresso
            *args, **kwargs: Argumentos para a função

        Returns:
            str: ID único da operação
        """

        # Criar worker
        if progress_callback:
            # Adicionar callback de progresso aos argumentos
            progress_cb = WorkerProgressCallback(None)  # Será definido após criação do worker
            kwargs['_progress_callback'] = progress_cb

        worker = EnhancedWorker(fn, *args, **kwargs)

        if progress_callback:
            # Configurar callback com referência ao worker
            progress_cb.worker = worker

        # Registrar operação
        operation_id = f"{name}_{id(worker)}"
        self.active_threads[operation_id] = worker
        self.thread_operations[operation_id] = {
            'name': name,
            'start_time': datetime.now(),
            'worker': worker
        }

        # Conectar sinais
        worker.signals.started.connect(lambda: self._on_thread_started(operation_id))
        worker.signals.finished.connect(lambda result: self._on_thread_finished(operation_id, result))
        worker.signals.error.connect(lambda error: self._on_thread_error(operation_id, error))
        worker.signals.cancelled.connect(lambda: self._on_thread_cancelled(operation_id))

        # Iniciar thread
        self.thread_pool.start(worker)

        logging.info(f"Thread iniciada: {operation_id}")
        return operation_id

    def cancel_operation(self, operation_id: str) -> bool:
        """
        Cancela operação específica.

        Args:
            operation_id: ID da operação

        Returns:
            bool: True se conseguiu cancelar
        """
        if operation_id in self.active_threads:
            worker = self.active_threads[operation_id]
            worker.cancel()
            return True
        return False

    def cancel_all_operations(self):
        """Cancela todas as operações ativas."""
        for operation_id in self.active_threads:
            self.active_threads[operation_id].cancel()
        logging.info("Todas as threads foram canceladas")

    def get_operation_status(self, operation_id: str) -> Optional[Dict[str, Any]]:
        """
        Retorna status de uma operação.

        Args:
            operation_id: ID da operação

        Returns:
            Dict com informações da operação ou None se não encontrada
        """
        if operation_id in self.thread_operations:
            op_info = self.thread_operations[operation_id].copy()
            op_info['is_active'] = operation_id in self.active_threads
            return op_info
        return None

    def get_active_operations(self) -> Dict[str, Dict[str, Any]]:
        """
        Retorna todas as operações ativas.

        Returns:
            Dict com operações ativas
        """
        active_ops = {}
        for op_id, op_info in self.thread_operations.items():
            if op_id in self.active_threads:
                active_ops[op_id] = op_info.copy()
                active_ops[op_id]['is_active'] = True
        return active_ops

    def _on_thread_started(self, operation_id: str):
        """Callback quando thread inicia."""
        self.thread_started.emit(self.thread_operations[operation_id]['name'])

    def _on_thread_finished(self, operation_id: str, result: Any):
        """Callback quando thread termina com sucesso."""
        self._cleanup_operation(operation_id)
        self.thread_finished.emit(self.thread_operations[operation_id]['name'])

        # Verificar se todas as threads terminaram
        if not self.active_threads:
            self.all_threads_finished.emit()

    def _on_thread_error(self, operation_id: str, error: tuple):
        """Callback quando thread tem erro."""
        error_msg = str(error[0])
        self._cleanup_operation(operation_id)
        self.thread_error.emit(self.thread_operations[operation_id]['name'], error_msg)

    def _on_thread_cancelled(self, operation_id: str):
        """Callback quando thread é cancelada."""
        self._cleanup_operation(operation_id)
        logging.info(f"Operação cancelada: {operation_id}")

    def _cleanup_operation(self, operation_id: str):
        """Remove operação da lista de ativas."""
        if operation_id in self.active_threads:
            del self.active_threads[operation_id]

    def _monitor_threads(self):
        """Monitora threads ativas e loga informações."""
        if self.active_threads:
            for operation_id, worker in self.active_threads.items():
                execution_time = time.time() - worker.start_time
                if execution_time > 30:  # Log se demorando mais de 30s
                    logging.warning(f"Thread {operation_id} executando há {execution_time:.1f}s")

    def get_stats(self) -> Dict[str, Any]:
        """
        Retorna estatísticas do gerenciador de threads.

        Returns:
            Dict com estatísticas
        """
        return {
            'active_threads': len(self.active_threads),
            'max_workers': self.thread_pool.maxThreadCount(),
            'available_workers': self.thread_pool.availableThreadCount(),
            'total_operations': len(self.thread_operations),
            'operations': list(self.thread_operations.keys())
        }

# Instância global do ThreadManager
thread_manager = ThreadManager()

# Funções de conveniência
def run_in_thread(name: str, fn: Callable, *args, progress_callback: bool = False, **kwargs) -> str:
    """
    Executa função em thread de forma simplificada.

    Args:
        name: Nome da operação
        fn: Função a executar
        progress_callback: Se incluir callback de progresso
        *args, **kwargs: Argumentos para a função

    Returns:
        str: ID da operação
    """
    return thread_manager.start_worker(name, fn, *args, progress_callback=progress_callback, **kwargs)

def cancel_operation(operation_id: str) -> bool:
    """Cancela operação por ID."""
    return thread_manager.cancel_operation(operation_id)

def cancel_all_threads():
    """Cancela todas as threads."""
    thread_manager.cancel_all_operations()

def get_thread_stats() -> Dict[str, Any]:
    """Retorna estatísticas das threads."""
    return thread_manager.get_stats()
