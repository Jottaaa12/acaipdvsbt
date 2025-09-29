
from PyQt6.QtCore import QObject, pyqtSignal, QThreadPool
from ui.worker import Worker
import database as db
from integrations.whatsapp_manager import WhatsAppManager
import json
from utils import get_data_path, format_currency

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

    def _send_whatsapp_notification(self, message):
        try:
            with open(get_data_path('config.json'), 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            whatsapp_config = config.get('whatsapp', {})
            notification_number = whatsapp_config.get('notification_number')

            if not notification_number:
                print("Número de telefone para notificações do WhatsApp não configurado.")
                return

            manager = WhatsAppManager.get_instance()
            if manager.is_ready:
                manager.send_message(notification_number, message)
                print(f"Notificação de caixa enviada para {notification_number}")
            else:
                print("WhatsApp não está conectado. Não foi possível enviar a notificação de caixa.")
        except Exception as e:
            print(f"Erro ao enviar notificação do WhatsApp: {e}")

    def _prepare_and_send_open_notification(self, session_id):
        report = db.get_cash_session_report(session_id)
        if not report or not report.get('session'):
            return

        session_data = report['session']
        user_name = session_data.get('username', 'N/A')
        open_time = session_data.get('open_time').strftime('%d/%m/%Y %H:%M')
        initial_amount = session_data.get('initial_amount', 0)

        message = (
            f"✅ *Caixa Aberto*\n\n"
            f"👤 *Usuário:* {user_name}\n"
            f"⏰ *Horário:* {open_time}\n"
            f"💰 *Valor Inicial:* {format_currency(initial_amount)}"
        )
        
        self._send_whatsapp_notification(message)

    def _prepare_and_send_close_notification(self, session_id):
        report = db.get_cash_session_report(session_id)
        if not report or not report.get('session'):
            return

        session_data = report['session']
        user_name = session_data.get('username', 'N/A')
        close_time = session_data.get('close_time').strftime('%d/%m/%Y %H:%M')
        expected = session_data.get('expected_amount', 0)
        counted = session_data.get('final_amount', 0)
        difference = session_data.get('difference', 0)
        observations = session_data.get('observations', 'Nenhuma')
        
        # New totals
        total_revenue = report.get('total_revenue', 0)
        total_after_sangria = report.get('total_after_sangria', 0)

        message = (
            f"🛑 *Caixa Fechado*\n\n"
            f"👤 *Usuário:* {user_name}\n"
            f"⏰ *Horário:* {close_time}\n\n"
            f"----------\n"
            f"📈 *Resumo Financeiro (Caixa Físico)*\n"
            f"----------\n"
            f"💰 *Valor Esperado:* {format_currency(expected)}\n"
            f"💵 *Valor Contado:* {format_currency(counted)}\n"
            f"⚖️ *Diferença:* {format_currency(difference, is_negative=(difference < 0))}\n\n"
            f"----------\n"
            f"📊 *Resumo de Vendas (Sessão)*\n"
            f"----------\n"
            f"💳 *Faturamento Bruto (Todas Formas):* {format_currency(total_revenue)}\n"
            f"💸 *Faturamento - Sangrias:* {format_currency(total_after_sangria)}\n\n"
            f"📝 *Observações:* {observations}"
        )
        
        self._send_whatsapp_notification(message)

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
            on_result=lambda result: self._on_close_session_result(result, session_id)
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
        """Lida com o resultado de db.open_cash_session."""
        session_id, message = result
        success = session_id is not None
        self.session_opened.emit(success, str(session_id) if success else message)
        if success:
            self._execute_worker(
                self._prepare_and_send_open_notification,
                session_id,
                on_result=lambda: print("Worker de notificação de abertura de caixa concluído."),
                on_error=lambda err: print(f"Erro no worker de notificação de abertura: {err}")
            )

    def _on_close_session_result(self, result, session_id):
        """Lida com o resultado de db.close_cash_session."""
        success, data = result
        message = "Caixa fechado com sucesso." if success else str(data)
        self.session_closed.emit(success, message)
        if success:
            self._execute_worker(
                self._prepare_and_send_close_notification,
                session_id,
                on_result=lambda: print("Worker de notificação de fechamento de caixa concluído."),
                on_error=lambda err: print(f"Erro no worker de notificação de fechamento: {err}")
            )

    def _on_get_status_result(self, result):
        '''Lida com o resultado de db.get_current_cash_session.'''
        self.status_updated.emit(result)
