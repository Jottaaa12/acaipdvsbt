# integrations/commands/aviso_command.py
from .base_command import ManagerCommand
from typing import List

# Importe o 'manager' type-hinting e o 'db'
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from integrations.whatsapp_manager import WhatsAppManager
import database as db

class AvisoCommand(ManagerCommand):
    """
    Envia uma mensagem de aviso para a tela do PDV e para todos os gerentes
    cadastrados no WhatsApp.
    """
    def __init__(self, args: List[str], user_id: str, chat_id: str, manager: 'WhatsAppManager'):
        """
        Inicializa o comando de aviso.
        """
        super().__init__(args, user_id, chat_id, manager)
    
    def execute(self) -> str:
        """
        Executa o envio de avisos.
        """
        if not self.args:
            return "⚠️ Por favor, forneça uma mensagem para o aviso. Ex: `/aviso Reunião hoje às 18h.`"

        message_to_send = " ".join(self.args)
        
        try:
            # --- 1. Enviar notificação para a tela do PDV ---
            # Esta função deve ser implementada no WhatsAppManager para interagir com a UI
            if hasattr(self.manager, 'show_ui_notification'):
                self.manager.show_ui_notification("📢 Aviso da Direção", message_to_send)
            
            # --- 2. Enviar notificação para o WhatsApp dos gerentes ---
            managers = db.get_authorized_managers()
            if not managers:
                return "✅ Aviso enviado para a tela. Nenhum gerente com WhatsApp cadastrado para notificar."

            sent_count = 0
            notification_message = f"📢 *Aviso da Direção:*\n\n{message_to_send}"
            
            # Usamos um set para evitar enviar mensagens duplicadas se houver números repetidos
            unique_phones = set()
            for phone in managers:
                validation = self.manager.config.validate_phone(phone)
                if validation['valid']:
                    unique_phones.add(validation['normalized'])

            # Normaliza o ID do usuário que enviou o comando para comparar
            sender_validation = self.manager.config.validate_phone(self.user_id)
            sender_normalized_phone = sender_validation['normalized'] if sender_validation['valid'] else None

            for phone in unique_phones:
                # Evita que o aviso seja enviado de volta para quem o enviou
                # Compara apenas telefones normalizados
                if phone != sender_normalized_phone:
                    self.manager.send_message(phone, notification_message, message_type='system_automatic')
                    sent_count += 1
            
            response = f"✅ Aviso enviado com sucesso!\n\n🖥️ 1 notificação na tela do PDV.\n📱 {sent_count} notificações enviadas pelo WhatsApp."
            
            return response
            
        except Exception as e:
            # CORREÇÃO: Trocado 'self.logging.error' por 'self.manager.logger.log_error'
            # O manager (ou a classe base) é quem deve possuir o logger.
            if hasattr(self.manager, 'logger') and hasattr(self.manager.logger, 'log_error'):
                self.manager.logger.log_error(f"Erro ao executar o comando /aviso: {e}", exc_info=True)
            else:
                # Fallback caso o logger não esteja onde esperamos
                print(f"Erro ao executar o comando /aviso: {e}")
                
            return "❌ Ocorreu um erro interno ao tentar enviar o aviso."