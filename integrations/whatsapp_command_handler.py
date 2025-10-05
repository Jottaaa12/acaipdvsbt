# Conteúdo para integrations/whatsapp_command_handler.py
import logging
from datetime import datetime, timedelta
import database as db
# A importação do WhatsAppManager foi removida para evitar importação circular

class CommandHandler:
    def __init__(self, manager):
        self.manager = manager
        self.authorized_managers = db.get_authorized_managers()
        logging.info(f"Gerentes autorizados no WhatsApp: {self.authorized_managers}")

    def process_command(self, command_data: dict):
        """Ponto de entrada para processar um comando recebido."""
        sender_phone = command_data.get('sender')
        command_text = command_data.get('text', '').strip()

        # Atualiza a lista de gerentes autorizados a cada comando para refletir mudanças em tempo real
        self.authorized_managers = db.get_authorized_managers()

        if not sender_phone or sender_phone not in self.authorized_managers:
            logging.warning(f"Comando de número não autorizado foi ignorado: {sender_phone}")
            return

        parts = command_text.split()
        command = parts[0].lower()
        args = parts[1:]

        # Mapeia o comando para a função correspondente
        command_map = {
            '/ajuda': self._handle_help,
            '/notificacoes': self._handle_notifications,
            '/vendas': self._handle_sales_report,
            '/relatorio': self._handle_sales_report, # Alias para /vendas
        }

        handler_func = command_map.get(command)
        if handler_func:
            response = handler_func(args)
        else:
            response = f"Comando '{command}' não reconhecido. Digite '/ajuda' para ver a lista de comandos."

        if response:
            self.manager.send_message(sender_phone, response)

    def _handle_help(self, args):
        """Retorna a mensagem de ajuda com os comandos disponíveis."""
        return (
            "🤖 *Comandos Disponíveis PDV* 🤖\n\n"
            "*/vendas [período]*\n"
            "  Ex: `/vendas hoje`, `/vendas ontem`, `/vendas 7dias`\n\n"
            "*/relatorio [data_inicio] [data_fim]*\n"
            "  Ex: `/relatorio 2025-10-01 2025-10-03`\n\n"
            "*/notificacoes [on/off]*\n"
            "  Ex: `/notificacoes off`"
        )

    def _handle_notifications(self, args):
        """Ativa ou desativa as notificações."""
        if not args:
            return "Uso: /notificacoes [on/off]"

        status = args[0].lower()
        if status == 'on':
            db.set_global_notification_status(True)
            return "✅ Notificações de vendas e caixa foram *ATIVADAS*."
        elif status == 'off':
            db.set_global_notification_status(False)
            return "❌ Notificações de vendas e caixa foram *DESATIVADAS*."
        else:
            return "Opção inválida. Use 'on' para ativar ou 'off' para desativar."

    def _handle_sales_report(self, args):
        """Gera e retorna um relatório de vendas."""
        try:
            today = datetime.now().date()
            if not args or args[0].lower() == 'hoje':
                start_date, end_date = today, today
            elif args[0].lower() == 'ontem':
                start_date = end_date = today - timedelta(days=1)
            elif args[0].lower().endswith('dias'):
                days = int(args[0][:-4])
                start_date, end_date = today - timedelta(days=days-1), today
            elif len(args) == 2:
                start_date = datetime.strptime(args[0], '%Y-%m-%d').date()
                end_date = datetime.strptime(args[1], '%Y-%m-%d').date()
            else:
                return "Formato do relatório inválido. Use '/ajuda' para ver os exemplos."

            report = db.get_sales_report(start_date.isoformat(), end_date.isoformat())
            
            # Formata a resposta
            date_str = f"de {start_date.strftime('%d/%m')} a {end_date.strftime('%d/%m')}" if start_date != end_date else f"de {start_date.strftime('%d/%m/%Y')}"
            
            response = (
                f"📊 *Relatório de Vendas {date_str}*\n\n"
                f"💰 *Faturamento Total:* R$ {report['total_revenue']:.2f}\n"
                f"🛒 *Vendas Realizadas:* {report['total_sales_count']}\n"
                f"📈 *Ticket Médio:* R$ {report['average_ticket']:.2f}\n"
            )

            if report['payment_methods']:
                response += "\n*Vendas por Pagamento:*\n"
                for pm in report['payment_methods']:
                    response += f"  - {pm['payment_method']}: R$ {pm['total']:.2f}\n"

            return response
        except Exception as e:
            logging.error(f"Erro ao gerar relatório de vendas via comando: {e}")
            return "❌ Ocorreu um erro ao gerar o relatório. Verifique o formato das datas (AAAA-MM-DD)."
