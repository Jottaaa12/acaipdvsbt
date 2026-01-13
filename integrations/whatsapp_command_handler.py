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
from .commands.sistema_commands import StatusCommand, LogsCommand, SistemaCommand, DbStatusCommand
from .commands.aviso_command import AvisoCommand
from .commands.aviso_agendado_command import AvisoAgendadoCommand
from .commands.monitor_command import MonitorCommand, OuvirCommand
from .commands.fun_commands import (
    SorteioCommand, QuizCommand, PalavraDoDiaCommand, MemeCommand, ConselhoCommand,
    ElogioCommand, FraseCommand, MotivacaoCommand, PiadaCommand,
    AniversarioCommand, CumprimentoCommand,
    ClimaCommand, DolarCommand, NoticiaCommand
)
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
            '/db_status': DbStatusCommand,
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
            '/verificar_pdv': MonitorCommand,
            '/ouvir': OuvirCommand,
            # Comandos de diversão
            '/sorteio': SorteioCommand,
            '/quiz': QuizCommand,
            '/palavra_do_dia': PalavraDoDiaCommand,
            '/meme': MemeCommand,
            '/conselho': ConselhoCommand,
            '/elogio': ElogioCommand,
            '/frase': FraseCommand,
            '/motivacao': MotivacaoCommand,
            '/piada': PiadaCommand,
            '/aniversario': AniversarioCommand,
            '/cumprimento': CumprimentoCommand,
            '/clima': ClimaCommand,
            '/dolar': DolarCommand,
            '/noticia': NoticiaCommand,
        }

    def update_authorized_managers(self):
        """Atualiza a lista de gerentes autorizados a partir do banco de dados, normalizando os números."""
        logging.info("Atualizando a lista de gerentes autorizados para comandos do WhatsApp...")
        raw_managers = db.get_authorized_managers()

        normalized_managers = []
        for phone in raw_managers:
            if phone:
                # CORREÇÃO: Normalizar todos os números da mesma forma que o validate_phone faz
                # Primeiro limpar e depois aplicar a mesma lógica de normalização
                clean_phone = phone.strip().split('@')[0]  # Remove sufixo se existir
                clean_phone = ''.join(filter(str.isdigit, clean_phone))  # Remove não-dígitos

                if clean_phone:
                    # Aplicar a mesma normalização que validate_phone: adicionar 55 se não tiver
                    if not clean_phone.startswith('55'):
                        clean_phone = '55' + clean_phone

                    # Verificar se é um número brasileiro válido (11 ou 12 dígitos com 55)
                    if len(clean_phone) >= 11 and clean_phone.startswith('55'):
                        # Para fins de comparação, vamos usar apenas os dígitos após o 55
                        # Isso garante consistência: 5588981905006 será comparado como 88981905006
                        number_without_cc = clean_phone[2:]  # Remove '55'

                        # Se tiver 11 dígitos (já inclui 9), ou 10 dígitos (celular sem 9), normalizar
                        if len(number_without_cc) == 11:
                            # Já tem 9 dígito: 88981905006
                            normalized_managers.append(number_without_cc)
                        elif len(number_without_cc) == 10 and number_without_cc.startswith(('11','12','13','14','15','16','17','18','19','21','22','24','27','28','31','32','33','34','35','37','38','41','42','43','44','45','46','47','48','49','51','53','54','55','61','62','63','64','65','66','67','68','69','71','73','74','75','77','79','81','82','83','84','85','86','87','88','89','91','92','93','94','95','96','97','98','99')):
                            # Celular sem 9 dígito: adicionar 9
                            number_without_cc = number_without_cc[:2] + '9' + number_without_cc[2:]
                            normalized_managers.append(number_without_cc)
                        else:
                            # Número fixo ou inválido: manter como está
                            normalized_managers.append(number_without_cc)
                    else:
                        logging.warning(f"Número de gerente com formato inválido ignorado: {phone} (normalizado: {clean_phone})")
                else:
                    logging.warning(f"Número de gerente inválido no banco de dados ignorado: {phone}")

        # Armazena a lista limpa e sem duplicatas
        self.authorized_managers = sorted(list(set(normalized_managers)))
        logging.info(f"Gerentes autorizados (normalizados) no WhatsApp: {self.authorized_managers}")


    def process_command(self, user_id: str, chat_id: str, command_text: str, manager: 'WhatsAppManager') -> List[Tuple[str, str]]:
        """
        Processa um comando, registra a auditoria e retorna uma LISTA de tuplas de resposta.
        Recebe a instância do manager para acessar métodos de status e logging.
        Retorna: [(response_text, recipient_phone)] ou []
        """
        command_text = command_text.strip()

        # --- CORREÇÃO (PROBLEMA 2): VERIFICA O PREFIXO PRIMEIRO ---
        # Se a mensagem não começar com '/', ignora silenciosamente.
        if not command_text.startswith('/'):
            return []
        # --- FIM DA CORREÇÃO ---

        # Verificação especial para LIDs (Linked Device IDs)
        # LIDs têm formato como "123456789@l.id" e não podem ser validados como números normais
        is_lid = '@lid' in user_id.lower() or '@l.id' in user_id.lower()

        if is_lid:
            # Para LIDs, usa o número base para verificação de permissões
            # Remove qualquer sufixo e usa apenas os dígitos
            sender_phone_clean = ''.join(filter(str.isdigit, user_id))
            sender_phone_with_suffix = user_id  # Mantém o LID original para logging
        else:
            # Para números normais, faz validação completa
            validation = self.config.validate_phone(user_id)
            if not validation['valid']:
                logging.warning(f"Número de remetente com formato inválido foi ignorado: {user_id}")
                return []

            sender_phone_with_suffix = validation['normalized']
            # CORREÇÃO: Aplicar a mesma normalização usada na lista de autorizados
            # Remove o @s.whatsapp.net e depois extrai apenas os dígitos após o código do país
            jid_without_suffix = sender_phone_with_suffix.split('@')[0]  # Remove @s.whatsapp.net
            if jid_without_suffix.startswith('55') and len(jid_without_suffix) >= 11:
                # Remove o código do país (55) para comparar com a lista normalizada
                sender_phone_clean = jid_without_suffix[2:]  # 5588981905006 -> 88981905006
            else:
                sender_phone_clean = jid_without_suffix

        # LOG DE ENTRADA DO COMANDO para facilitar debug futuro
        logging.info(f"Processando comando '{command_text}' recebido de: {user_id} (Chat: {chat_id})")

        # A verificação agora usa a lista limpa em cache, baseada no autor da mensagem.
        if not sender_phone_clean or sender_phone_clean not in self.authorized_managers:
            logging.warning(f"Comando de número não autorizado foi ignorado: {sender_phone_clean}. (Autor original: {user_id}). Lista de autorizados: {self.authorized_managers}")
            # Log de tentativa de comando não autorizado
            manager.logger.log_command(sender=sender_phone_with_suffix, command=command_text, success=False, response_preview="Acesso negado - Número não autorizado")
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
                response_preview = response[:150] if response else ""
                manager.logger.log_command(sender=sender_phone_with_suffix, command=command_text, success=True, response_preview=response_preview)

            except Exception as e:
                logging.error(f"Erro ao executar o comando '{command_name}': {e}", exc_info=True)
                response = f"❌ Ocorreu um erro interno ao processar o comando '{command_name}'. A equipe de suporte foi notificada."
                manager.logger.log_command(sender=sender_phone_with_suffix, command=command_text, success=False, response_preview=str(e))
        else:
            response = f"Comando '{command_name}' não reconhecido. Digite '/ajuda' para ver a lista de comandos."
            manager.logger.log_command(sender=sender_phone_with_suffix, command=command_text, success=False, response_preview="Comando não reconhecido")

        if response:
            # A resposta é enviada para o chat_id (o grupo ou a conversa privada)
            return [(response, chat_id)]
        
        return []
