import logging
from datetime import datetime
from PyQt6.QtCore import QTimer, QObject, pyqtSignal
from config_manager import ConfigManager
from integrations.whatsapp_manager import WhatsAppManager # Assuming this exists and has a send method

class AvisoScheduler(QObject):
    """
    Agendador para enviar avisos automáticos via WhatsApp.
    Verifica as configurações de avisos agendados e envia mensagens
    nos horários e dias especificados.
    """

    notification_sent = pyqtSignal(str)    # Mensagem de sucesso
    notification_failed = pyqtSignal(str)  # Mensagem de erro

    def __init__(self, whatsapp_manager: WhatsAppManager):
        super().__init__()
        self.config_manager = ConfigManager()
        self.whatsapp_manager = whatsapp_manager
        self.timer = QTimer()
        self.timer.timeout.connect(self.check_and_send_notifications)
        self.last_check_minute = -1 # Para garantir que só envie uma vez por minuto

        logging.info("AvisoScheduler inicializado.")

    def start_scheduler(self):
        """Inicia o agendador para verificar notificações a cada minuto."""
        self.timer.start(60 * 1000) # Verifica a cada 60 segundos (1 minuto)
        logging.info("AvisoScheduler iniciado. Verificando a cada minuto.")

    def stop_scheduler(self):
        """Para o agendador."""
        self.timer.stop()
        logging.info("AvisoScheduler parado.")

    def check_and_send_notifications(self):
        """
        Verifica as notificações agendadas e envia as que correspondem
        ao horário e dia atuais.
        """
        now = datetime.now()
        current_time_str = now.strftime("%H:%M")
        current_day_of_week = now.strftime("%a").lower() # Ex: 'seg', 'ter', 'qua'

        # Mapeamento de dias da semana para o formato usado no config (se necessário)
        day_map = {
            "mon": "Seg", "tue": "Ter", "wed": "Qua", "thu": "Qui",
            "fri": "Sex", "sat": "Sáb", "sun": "Dom"
        }
        current_day_of_week_pt = day_map.get(current_day_of_week, "")

        # Garante que a verificação e envio ocorra apenas uma vez por minuto
        if now.minute == self.last_check_minute:
            return
        self.last_check_minute = now.minute

        logging.debug(f"Verificando avisos agendados em {current_time_str} de {current_day_of_week_pt}...")

        notifications = self.config_manager.get_scheduled_notifications()

        for notification in notifications:
            if not notification.get('ativo', False):
                continue # Ignora notificações inativas

            scheduled_time = notification.get('horario')
            scheduled_days = notification.get('dias_semana', [])
            message = notification.get('mensagem')
            numbers = notification.get('numeros', [])
            sender = notification.get('remetente', 'Sistema PDV')
            notification_id = notification.get('id', 'unknown')

            if scheduled_time == current_time_str and current_day_of_week_pt in scheduled_days:
                logging.info(f"Aviso agendado '{notification_id}' acionado para envio.")
                for number in numbers:
                    try:
                        # Usar o método send_message do WhatsApp manager
                        result = self.whatsapp_manager.send_message(number, message, message_type='system_automatic')
                        if not result.get('success', False):
                            error_msg = result.get('error', 'Erro desconhecido')
                            logging.error(f"Falha ao enviar aviso agendado para {number}: {error_msg}")
                            self.notification_failed.emit(f"Aviso agendado falhou para {number}: {error_msg}")
                            continue
                        log_msg = f"Aviso '{notification_id}' enviado para {number} (Remetente: {sender})."
                        logging.info(log_msg)
                        self.notification_sent.emit(log_msg)
                    except Exception as e:
                        error_msg = f"Falha ao enviar aviso '{notification_id}' para {number}: {e}"
                        logging.error(error_msg, exc_info=True)
                        self.notification_failed.emit(error_msg)
