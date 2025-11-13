# integrations/whatsapp_command_handler.py
import logging
from typing import List, Dict, Any, Type, Tuple

# Importe o 'manager' type-hinting
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from integrations.whatsapp_manager import WhatsAppManager

# Importe a base e TODOS os seus novos comandos
from .commands.base_command import BaseCommand, ManagerCommand
from .commands.help_command import HelpCommand
from .commands.fiado_commands import FiadoCommand
from .commands.caixa_commands import CaixaCommand
from .commands.produto_commands import ProdutoCommand
from .commands.estoque_commands import EstoqueCommand
from .commands.relatorio_commands import SalesReportCommand, DashboardCommand, ProdutosVendidosCommand
from .commands.admin_commands import NotificationsCommand, BackupCommand, GerenteCommand
from .commands.sistema_commands import StatusCommand, LogsCommand, SistemaCommand
from .commands.aviso_command import AvisoCommand
from .commands.aviso_agendado_command import AvisoAgendadoCommand
from .whatsapp_config import get_whatsapp_config
import database as db

class CommandHandler:
    def __init__(self):
        self.config = get_whatsapp_config()
        self.authorized_managers = []
        self.update_authorized_managers()  # Carga inicial
        
        # O novo Command Map mapeia strings para CLASSES
        self.command_map: Dict[str, Type[BaseCommand]] = {
            '/ajuda': HelpCommand,
            '/notificacoes': NotificationsCommand,
            '/vendas': SalesReportCommand,
            '/relatorio': SalesReportCommand,  # Alias
            '/status': StatusCommand,
            '/logs': LogsCommand,
            '/caixa': CaixaCommand,
            '/produto': ProdutoCommand,
            '/estoque': EstoqueCommand,
            '/backup': BackupCommand,
            '/gerente': GerenteCommand,
            '/dashboard': DashboardCommand,
            '/produtos_vendidos': ProdutosVendidosCommand,
            '/sistema': SistemaCommand,
            '/fiado': FiadoCommand,
            '/fiados': FiadoCommand, # Alias
            '/aviso': AvisoCommand,
            '/aviso_agendado': AvisoAgendadoCommand,
        }

    def update_authorized_managers(self):
        """Atualiza a lista de gerentes autorizados a partir do banco de dados, normalizando os números."""
        logging.info("Atualizando a lista de gerentes autorizados para comandos do WhatsApp...")
        raw_managers = db.get_authorized_managers()
        
        normalized_managers = []
        for phone in raw_managers:
            if phone:
                validation = self.config.validate_phone(phone)
                if validation['valid']:
                    normalized_managers.append(validation['normalized'])
                else:
                    logging.warning(f"Número de gerente inválido no banco de dados ignorado: {phone}")

        self.authorized_managers = normalized_managers
        logging.info(f"Gerentes autorizados (normalizados) no WhatsApp: {self.authorized_managers}")


    def process_command(self, user_id: str, chat_id: str, command_text: str, manager: 'WhatsAppManager') -> List[Tuple[str, str]]:
        """
        Processa um comando, registra a auditoria e retorna uma LISTA de tuplas de resposta.
        Recebe a instância do manager para acessar métodos de status e logging.
        Retorna: [(response_text, recipient_phone)] ou []
        """
        command_text = command_text.strip()

        # Normaliza o número do remetente (user_id) para verificação de permissão
        validation = self.config.validate_phone(user_id)
        if not validation['valid']:
            logging.warning(f"Número de remetente com formato inválido foi ignorado: {user_id}")
            return []
        
        sender_phone = validation['normalized']

        # A verificação agora usa a lista normalizada em cache, baseada no autor da mensagem.
        if not sender_phone or sender_phone not in self.authorized_managers:
            logging.warning(f"Comando de número não autorizado foi ignorado: {sender_phone} (Lista de autorizados: {self.authorized_managers})")
            # Log de tentativa de comando não autorizado
            manager.logger.log_command(sender=sender_phone, command=command_text, success=False, response_preview="Acesso negado")
            return []

        parts = command_text.split()
        command_name = parts[0].lower()
        args = parts[1:]

        # --- LÓGICA DE DESPACHO (O CORAÇÃO DA MUDANÇA) ---
        CommandClass = self.command_map.get(command_name)

        if CommandClass:
            try:
                # Instancia o comando, agora passando user_id e chat_id
                if issubclass(CommandClass, ManagerCommand):
                    # Se for um ManagerCommand, injeta a dependência do manager
                    command_instance = CommandClass(args, user_id=user_id, chat_id=chat_id, manager=manager)
                else:
                    # Senão, é um BaseCommand e só precisa dos args, user_id e chat_id
                    command_instance = CommandClass(args, user_id=user_id, chat_id=chat_id)

                # Executa o comando
                response = command_instance.execute()
                
                # Log de sucesso
                manager.logger.log_command(sender=sender_phone, command=command_text, success=True, response_preview=response[:150])

            except Exception as e:
                logging.error(f"Erro ao executar o comando '{command_name}': {e}", exc_info=True)
                response = f"❌ Ocorreu um erro interno ao processar o comando '{command_name}'. A equipe de suporte foi notificada."
                manager.logger.log_command(sender=sender_phone, command=command_text, success=False, response_preview=str(e))
        else:
            response = f"Comando '{command_name}' não reconhecido. Digite '/ajuda' para ver a lista de comandos."
            manager.logger.log_command(sender=sender_phone, command=command_text, success=False, response_preview="Comando não reconhecido")

        if response:
            # A resposta é enviada para o chat_id (o grupo ou a conversa privada)
            return [(response, chat_id)]
        
        return []