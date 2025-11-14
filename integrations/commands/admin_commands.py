# integrations/commands/admin_commands.py
from .base_command import BaseCommand, ManagerCommand
from typing import List, TYPE_CHECKING
from integrations.whatsapp_config import get_whatsapp_config

if TYPE_CHECKING:
    from integrations.whatsapp_manager import WhatsAppManager

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
    def __init__(self, args: List[str], user_id: str, chat_id: str, manager: 'WhatsAppManager'):
        super().__init__(args, user_id, chat_id, manager)
        self.config = get_whatsapp_config()

    def _get_clean_number_list(self) -> List[str]:
        """Carrega a lista de gerentes e a limpa, removendo sufixos e duplicatas."""
        numbers_str = self.db.load_setting('whatsapp_manager_numbers', '')
        # CORREÇÃO: Limpa os números no carregamento, removendo sufixos
        clean_numbers = set()
        for num in numbers_str.split(','):
            if num.strip():
                clean_numbers.add(num.strip().split('@')[0])
        
        # Retorna uma lista ordenada
        return sorted(list(clean_numbers))

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
        # CORREÇÃO: Usa a função helper para obter a lista limpa
        numbers = self._get_clean_number_list()
        if not numbers:
            return "ℹ️ Nenhum gerente cadastrado."
        
        response = "👨‍💼 *Gerentes Autorizados*\n\n"
        for num in numbers:
            # Números já estão limpos
            response += f"- `{num}`\n"
        return response

    def _handle_gerente_adicionar(self, args: List[str]) -> str:
        """Adiciona um novo gerente."""
        if len(args) != 1:
            return "Uso: /gerente adicionar <número_telefone>"
        
        new_number_input = args[0]
        validation = self.config.validate_phone(new_number_input)
        if not validation['valid']:
            return f"❌ Número '{new_number_input}' inválido."

        # CORREÇÃO: Pega o número normalizado e remove o sufixo para salvar
        normalized_number = validation['normalized']
        number_to_store = normalized_number.split('@')[0]
        
        # CORREÇÃO: Carrega a lista limpa
        numbers = self._get_clean_number_list()

        if number_to_store in numbers:
            return f"ℹ️ O número `{number_to_store}` já é um gerente."

        numbers.append(number_to_store)
        self.db.save_setting('whatsapp_manager_numbers', ",".join(numbers))
        self.manager.update_authorized_users()  # Atualiza em tempo real

        return f"✅ Novo gerente `{number_to_store}` adicionado com sucesso."

    def _handle_gerente_remover(self, args: List[str]) -> str:
        """Remove um gerente."""
        if len(args) != 1:
            return "Uso: /gerente remover <número_telefone>"

        number_to_remove_input = args[0]
        
        # CORREÇÃO: Precisamos validar, mas também limpar o input para comparar
        # com a lista limpa.
        
        # Tenta validar primeiro
        validation = self.config.validate_phone(number_to_remove_input)
        if validation['valid']:
            # Se válido, usa a forma normalizada limpa
            number_to_remove = validation['normalized'].split('@')[0]
        else:
            # Se inválido (ex: usuário digitou número curto), limpa o input
            number_to_remove = number_to_remove_input.strip().split('@')[0]

        # CORREÇÃO: Carrega a lista limpa
        numbers = self._get_clean_number_list()

        if number_to_remove not in numbers:
            return f"ℹ️ O número `{number_to_remove}` não foi encontrado na lista de gerentes."

        numbers.remove(number_to_remove)
        self.db.save_setting('whatsapp_manager_numbers', ",".join(numbers))
        self.manager.update_authorized_users()  # Atualiza em tempo real

        return f"✅ Gerente `{number_to_remove}` removido com sucesso."
