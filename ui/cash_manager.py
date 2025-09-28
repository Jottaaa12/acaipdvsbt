
from PyQt6.QtCore import QObject, pyqtSignal, QThreadPool
from ui.worker import Worker
import database as db

class CashManager(QObject):
    '''
    Gerencia operações de caixa de forma assíncrona usando um QThreadPool.
    Isso evita que a interface do usuário congele durante as operações de banco de dados.
    '''
    
    # Sinal emitido após a tentativa de abrir uma sessão.
    # bool: sucesso, str: mensagem ou ID da sessão
    session_opened = pyqtSignal(bool, str)
    
    # Sinal emitido após a tentativa de fechar uma sessão.
    # bool: sucesso, str: mensagem
    session_closed = pyqtSignal(bool, str)

    # Sinal emitido com o status atual do caixa.
    # dict: dados da sessão ou None se fechado
    status_updated = pyqtSignal(object)

    def __init__(self):
        super().__init__()
        self.thread_pool = QThreadPool()
        print("CashManager inicializado. Usando QThreadPool.")

    def _execute_worker(self, fn, *args, on_result, on_error=None, on_finished=None):
        '''Cria e executa um worker para a função fornecida.'''
        worker = Worker(fn, *args)
        worker.signals.result.connect(on_result)
        if on_error:
            worker.signals.error.connect(on_error)
        if on_finished:
            worker.signals.finished.connect(on_finished)
        
        self.thread_pool.start(worker)

    # --- Funções Públicas para Chamar Operações ---

    def open_session_async(self, user_id, initial_amount):
        '''
        Abre uma sessão de caixa em uma thread separada.
        '''
        self._execute_worker(
            db.open_cash_session,
            user_id,
            initial_amount,
            on_result=self._on_open_session_result
        )

    def close_session_async(self, session_id, user_id, final_amount, cash_counts, observations):
        '''
        Fecha uma sessão de caixa em uma thread separada.
        '''
        self._execute_worker(
            db.close_cash_session,
            session_id, user_id, final_amount, cash_counts, observations,
            on_result=self._on_close_session_result
        )

    def get_status_async(self):
        '''
        Busca o status da sessão de caixa atual em uma thread separada.
        '''
        self._execute_worker(
            db.get_current_cash_session,
            on_result=self._on_get_status_result
        )

    # --- Slots Privados para Lidar com Resultados dos Workers ---

    def _on_open_session_result(self, result):
        '''Lida com o resultado de db.open_cash_session.'''
        session_id, message = result
        success = session_id is not None
        self.session_opened.emit(success, str(session_id) if success else message)

    def _on_close_session_result(self, result):
        '''Lida com o resultado de db.close_cash_session.'''
        success, data = result
        message = "Caixa fechado com sucesso." if success else str(data)
        self.session_closed.emit(success, message)

    def _on_get_status_result(self, result):
        '''Lida com o resultado de db.get_current_cash_session.'''
        self.status_updated.emit(result)
