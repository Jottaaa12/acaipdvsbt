# integrations/commands/aviso_agendado_command.py
from .base_command import ManagerCommand  # Alterado de BaseCommand para ManagerCommand
from config_manager import ConfigManager
import uuid
import re
from typing import List

# Importe o 'manager' type-hinting
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from integrations.whatsapp_manager import WhatsAppManager


class AvisoAgendadoCommand(ManagerCommand):  # Alterado de BaseCommand para ManagerCommand
    """
    Gerencia avisos agendados via comandos do WhatsApp.
    Subcomandos: agendar, listar, remover.
    """
    def __init__(self, args: List[str], user_id: str, chat_id: str, manager: 'WhatsAppManager'):
        # Adicionado 'manager' para alinhar com ManagerCommand
        super().__init__(args, user_id, chat_id, manager)
        self.config_manager = ConfigManager()

    def execute(self) -> str:
        if not self.args:
            return self._get_help()

        subcommand = self.args[0].lower()
        command_args = self.args[1:]

        if subcommand == 'agendar':
            return self._handle_agendar(command_args)
        elif subcommand == 'listar':
            return self._handle_listar()
        elif subcommand == 'remover':
            return self._handle_remover(command_args)
        else:
            return self._get_help()

    def _get_help(self) -> str:
        # CORREÇÃO: A string "*Exemplo..." estava aberta (sem aspas de fechamento)
        return (
            "Gerenciador de Avisos Agendados\n\n"
            "Uso: /aviso_agendado [subcomando] [argumentos]\n\n"
            "Subcomandos:\n"
            "  `listar` - Mostra todos os avisos agendados.\n"
            "  `remover <id>` - Remove um aviso pelo ID.\n"
            "  `agendar <HH:MM> <dias> <numeros> <mensagem>` - Agenda um novo aviso.\n\n"
            "*Exemplo de agendamento:*\n"  # <-- Linha corrigida
            "/aviso_agendado agendar 14:30 seg,ter,qua +55119...1,+55219...2 Lembrete de reunião"
        )

    def _handle_listar(self) -> str:
        notifications = self.config_manager.get_scheduled_notifications()
        if not notifications:
            return "Nenhum aviso agendado encontrado."

        response = "📋 *Avisos Agendados:*\n\n"
        for notif in notifications:
            dias = ", ".join(notif.get('dias_semana', []))
            numeros = ", ".join(notif.get('numeros', []))
            status = "Ativo" if notif.get('ativo', False) else "Inativo"
            response += (
                f"🆔 *ID:* `{notif.get('id')}`\n"
                f"  - 🕒 *Horário:* {notif.get('horario', 'N/A')}\n"
                f"  - 🗓️ *Dias:* {dias}\n"
                f"  - 📞 *Números:* {numeros}\n"
                f"  - 💬 *Mensagem:* \"{notif.get('mensagem', '')}\"\n"
                f"  - 🟢 *Status:* {status}\n\n"
            )
        return response

    def _handle_remover(self, args: List[str]) -> str:
        if not args:
            return "Por favor, forneça o ID do aviso a ser removido. Ex: /aviso_agendado remover <id>"

        notification_id = args[0]
        notifications = self.config_manager.get_scheduled_notifications()
        
        if not any(n.get('id') == notification_id for n in notifications):
            return f"❌ Erro: Nenhum aviso encontrado com o ID `{notification_id}`."

        try:
            self.config_manager.delete_scheduled_notification(notification_id)
            return f"✅ Aviso com ID `{notification_id}` removido com sucesso."
        except Exception as e:
            # CORREÇÃO: Trocado 'self.logging.error' por 'self.manager.logger.log_error'
            self.manager.logger.log_error(f"Erro ao remover aviso agendado via comando: {e}", exc_info=True)
            return "❌ Ocorreu um erro interno ao tentar remover o aviso."

    def _handle_agendar(self, args: List[str]) -> str:
        if len(args) < 4:
            # CORREÇÃO: A string "Ex:..." não estava terminada (faltava '`"')
            return (
                "Argumentos insuficientes para agendar.\n\n"
                "Formato: `agendar <HH:MM> <dias> <numeros> <mensagem>`\n"
                "Ex: `agendar 08:00 seg,ter,qua +55119...1,+55219...2 Bom dia!`"  # <-- Linha corrigida
            )

        # 1. Horário (HH:MM)
        time_str = args[0]
        if not re.match(r'^([01]\d|2[0-3]):([0-5]\d)$', time_str):
            return f"❌ Formato de horário inválido: '{time_str}'. Use HH:MM (ex: 08:30)."

        # 2. Dias da semana (seg,ter,qua...)
        days_str = args[1].lower()
        days_list = [day.strip() for day in days_str.split(',')]
        
        # Corrigindo 'sab' para 'Sáb' para corresponder ao que a UI espera
        days_list_corrected = []
        day_map = {"seg": "Seg", "ter": "Ter", "qua": "Qua", "qui": "Qui", "sex": "Sex", "sab": "Sáb", "dom": "Dom"}
        
        for day in days_list:
            if day in day_map:
                days_list_corrected.append(day_map[day])
            else:
                return f"❌ Dia da semana inválido: '{day}'. Use seg, ter, qua, qui, sex, sab, dom."

        if not days_list_corrected:
            return "❌ Nenhum dia da semana válido fornecido."

        # 3. Números de telefone (+55...,+55...)
        numbers_str = args[2]
        numbers_list = [num.strip() for num in numbers_str.split(',') if num.strip()]
        if not numbers_list:
            return "❌ Nenhum número de telefone fornecido."

        # 4. Mensagem
        message = " ".join(args[3:])
        if not message:
            return "❌ A mensagem não pode estar vazia."

        notification_data = {
            'id': str(uuid.uuid4()),
            'remetente': 'Sistema PDV (via WhatsApp)',
            'mensagem': message,
            'numeros': numbers_list,
            'horario': time_str,
            'dias_semana': days_list_corrected,
            'ativo': True
        }

        try:
            self.config_manager.add_scheduled_notification(notification_data)
            return (
                f"✅ Aviso agendado com sucesso!\n\n"
                f"🆔 *ID:* `{notification_data['id']}`\n"
                f"🕒 *Horário:* {time_str}\n"
                f"🗓️ *Dias:* {', '.join(days_list_corrected)}\n"
                f"📞 *Números:* {', '.join(numbers_list)}\n"
                f"💬 *Mensagem:* \"{message}\""
            )
        except Exception as e:
            # CORREÇÃO: Trocado 'self.logging.error' por 'self.manager.logger.log_error'
            self.manager.logger.log_error(f"Erro ao agendar aviso via comando: {e}", exc_info=True)
            return "❌ Ocorreu um erro interno ao salvar o agendamento."