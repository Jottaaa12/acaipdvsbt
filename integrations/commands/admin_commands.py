# integrations/commands/admin_commands.py
from .base_command import BaseCommand, ManagerCommand
from typing import List
from integrations.whatsapp_config import get_whatsapp_config

class NotificationsCommand(BaseCommand):
    """Ativa ou desativa as notificações."""
    def execute(self) -> str:
        if not self.args:
            return "Uso: /notificacoes [on/off]"

        status = self.args[0].lower()
        if status == 'on':
            self.db.set_global_notification_status(True)
            return "✅ Notificações de vendas e caixa foram *ATIVADAS*."
        elif status == 'off':
            self.db.set_global_notification_status(False)
            return "❌ Notificações de vendas e caixa foram *DESATIVADAS*."
        else:
            return "Opção inválida. Use 'on' para ativar ou 'off' para desativar."

class BackupCommand(BaseCommand):
    """Inicia a rotina de backup do banco de dados."""
    def execute(self) -> str:
        try:
            success, message = self.db.create_backup()
            if success:
                return f"✅ Backup do banco de dados criado com sucesso em: `{message}`"
            else:
                return f"❌ Falha ao criar backup: {message}"
        except Exception as e:
            self.logging.error(f"Erro ao iniciar backup via comando: {e}", exc_info=True)
            return "❌ Ocorreu um erro interno ao tentar criar o backup."

class GerenteCommand(ManagerCommand):
    """Lida com subcomandos de gerenciamento de gerentes."""
    def __init__(self, args: List[str], manager: 'WhatsAppManager'):
        super().__init__(args, manager)
        self.config = get_whatsapp_config()

    def execute(self) -> str:
        if not self.args:
            return "Uso: /gerente [listar|adicionar|remover]"

        subcommand = self.args[0].lower()
        command_args = self.args[1:]

        if subcommand == 'listar':
            return self._handle_gerente_listar()
        elif subcommand == 'adicionar':
            return self._handle_gerente_adicionar(command_args)
        elif subcommand == 'remover':
            return self._handle_gerente_remover(command_args)
        else:
            return f"Subcomando '/gerente {subcommand}' não reconhecido."

    def _handle_gerente_listar(self) -> str:
        """Lista os gerentes autorizados."""
        numbers_str = self.db.load_setting('whatsapp_manager_numbers', '')
        if not numbers_str:
            return "ℹ️ Nenhum gerente cadastrado."
        
        numbers = [num.strip() for num in numbers_str.split(',')]
        response = "👨‍💼 *Gerentes Autorizados*\n\n"
        for num in numbers:
            response += f"- `{num}`\n"
        return response

    def _handle_gerente_adicionar(self, args: List[str]) -> str:
        """Adiciona um novo gerente."""
        if len(args) != 1:
            return "Uso: /gerente adicionar <número_telefone>"
        
        new_number = args[0]
        validation = self.config.validate_phone(new_number)
        if not validation['valid']:
            return f"❌ Número '{new_number}' inválido."

        normalized_number = validation['normalized']
        
        numbers_str = self.db.load_setting('whatsapp_manager_numbers', '')
        numbers = [num.strip() for num in numbers_str.split(',') if num.strip()]

        if normalized_number in numbers:
            return f"ℹ️ O número `{normalized_number}` já é um gerente."

        numbers.append(normalized_number)
        self.db.save_setting('whatsapp_manager_numbers', ",".join(numbers))
        self.manager.update_authorized_users()  # Atualiza em tempo real

        return f"✅ Novo gerente `{normalized_number}` adicionado com sucesso."

    def _handle_gerente_remover(self, args: List[str]) -> str:
        """Remove um gerente."""
        if len(args) != 1:
            return "Uso: /gerente remover <número_telefone>"

        number_to_remove = args[0]
        validation = self.config.validate_phone(number_to_remove)
        if not validation['valid']:
            return f"❌ Número '{number_to_remove}' inválido."
        
        normalized_number = validation['normalized']

        numbers_str = self.db.load_setting('whatsapp_manager_numbers', '')
        numbers = [num.strip() for num in numbers_str.split(',') if num.strip()]

        if normalized_number not in numbers:
            return f"ℹ️ O número `{normalized_number}` não foi encontrado na lista de gerentes."

        numbers.remove(normalized_number)
        self.db.save_setting('whatsapp_manager_numbers', ",".join(numbers))
        self.manager.update_authorized_users()  # Atualiza em tempo real

        return f"✅ Gerente `{normalized_number}` removido com sucesso."
