# integrations/commands/relatorio_commands.py
from .base_command import BaseCommand
from datetime import datetime, timedelta

class SalesReportCommand(BaseCommand):
    """Gera e retorna um relatório de vendas."""
    def execute(self) -> str:
        try:
            today = datetime.now().date()
            if not self.args or self.args[0].lower() == 'hoje':
                start_date, end_date = today, today
            elif self.args[0].lower() == 'ontem':
                start_date = end_date = today - timedelta(days=1)
            elif self.args[0].lower().endswith('dias'):
                days = int(self.args[0][:-4])
                start_date, end_date = today - timedelta(days=days-1), today
            elif len(self.args) == 2:
                start_date = datetime.strptime(self.args[0], '%Y-%m-%d').date()
                end_date = datetime.strptime(self.args[1], '%Y-%m-%d').date()
            else:
                return "Formato do relatório inválido. Use '/ajuda' para ver os exemplos."

            report = self.db.get_sales_report(start_date.isoformat(), end_date.isoformat())
            
            date_str = f"de `{start_date.strftime('%d/%m')}` a `{end_date.strftime('%d/%m')}`" if start_date != end_date else f"em `{start_date.strftime('%d/%m/%Y')}`"
            
            response = (
                f"📊 *Relatório de Vendas ({date_str})*\n\n"
                f"💰 *Faturamento Total:* `R$ {report['total_revenue']:.2f}`\n"
                f"🛒 *Vendas Realizadas:* `{report['total_sales_count']}`\n"
                f"📈 *Ticket Médio:* `R$ {report['average_ticket']:.2f}`\n"
            )

            if report['payment_methods']:
                response += "\n💳 *Vendas por Pagamento:*\n"
                for pm in report['payment_methods']:
                    response += f"  - {pm['payment_method']}: `R$ {pm['total']:.2f}`\n"
            
            cash_status = self.db.get_current_cash_status()
            if cash_status and cash_status['status'] == 'ABERTO':
                response += f"\n\n📦 *Caixa Atual (Aberto por {cash_status['username']})*\n"
                response += f"  - Saldo em Dinheiro: `R$ {cash_status['current_balance']:.2f}`"

            return response
        except ValueError:
            self.logging.warning(f"Comando de relatório de vendas com formato de data inválido: {self.args}")
            return "🗓️ Formato de data inválido. Use AAAA-MM-DD, por exemplo: `/relatorio 2025-10-01 2025-10-05`."
        except Exception as e:
            self.logging.error(f"Erro inesperado ao gerar relatório de vendas via comando: {e}", exc_info=True)
            return "❌ Ocorreu um erro interno ao gerar o relatório. A equipe de suporte foi notificada."

class DashboardCommand(BaseCommand):
    """Retorna um dashboard com o resumo do dia."""
    def execute(self) -> str:
        try:
            today_str = datetime.now().date().isoformat()
            report = self.db.get_sales_report(today_str, today_str)
            cash_status = self.db.get_current_cash_status()

            top_product = report['top_products'][0]['description'] if report['top_products'] else "N/A"

            response = f"📈 *Dashboard do Dia ({datetime.now().strftime('%d/%m/%Y')})*\n\n"
            
            response += "📊 *Vendas:*\n"
            response += f"  - Faturamento Total: `R$ {report['total_revenue']:.2f}`\n"
            response += f"  - Vendas Realizadas: `{report['total_sales_count']}`\n"
            response += f"  - Ticket Médio: `R$ {report['average_ticket']:.2f}`\n"
            response += f"  - Produto Mais Vendido: `{top_product}`\n\n"

            response += "📦 *Caixa:*\n"
            if cash_status.get('status') == 'ABERTO':
                response += f"  - Status: `Aberto por {cash_status['username']}`\n"
                response += f"  - Saldo em Dinheiro: `R$ {cash_status['current_balance']:.2f}`\n"
            else:
                response += "  - Status: `Fechado`\n"

            return response

        except Exception as e:
            self.logging.error(f"Erro ao gerar dashboard via comando: {e}", exc_info=True)
            return "❌ Ocorreu um erro interno ao gerar o dashboard."

class ProdutosVendidosCommand(BaseCommand):
    """Retorna um ranking dos produtos mais vendidos em um período."""
    def execute(self) -> str:
        try:
            today = datetime.now().date()
            if not self.args or self.args[0].lower() == 'hoje':
                start_date, end_date = today, today
            elif self.args[0].lower() == 'ontem':
                start_date = end_date = today - timedelta(days=1)
            elif self.args[0].lower().endswith('dias'):
                days = int(self.args[0][:-4])
                start_date, end_date = today - timedelta(days=days-1), today
            elif len(self.args) == 2:
                start_date = datetime.strptime(self.args[0], '%Y-%m-%d').date()
                end_date = datetime.strptime(self.args[1], '%Y-%m-%d').date()
            else:
                return "Formato do período inválido. Use 'hoje', 'ontem', '7dias' ou um intervalo de datas."

            report = self.db.get_sales_report(start_date.isoformat(), end_date.isoformat())
            top_products = report.get('top_products', [])

            if not top_products:
                return "ℹ️ Nenhuma venda de produto registrada no período."

            date_str = f"de {start_date.strftime('%d/%m')} a {end_date.strftime('%d/%m')}" if start_date != end_date else f"em {start_date.strftime('%d/%m/%Y')}"
            response = f"🏆 *Produtos Mais Vendidos ({date_str})*\n\n"
            
            for i, product in enumerate(top_products[:10]):
                emoji = "🥇" if i == 0 else "🥈" if i == 1 else "🥉" if i == 2 else f"{i+1}."
                quantity_str = f"{product['quantity_sold']:.3f}".replace('.', ',')
                response += f"{emoji} `{product['description']}`\n"
                response += f"    - Quantidade: `{quantity_str}`\n"
                response += f"    - Faturamento: `R$ {product['revenue']:.2f}`\n"

            return response.strip()

        except ValueError:
            return "🗓️ Formato de data inválido. Use AAAA-MM-DD."
        except Exception as e:
            self.logging.error(f"Erro ao gerar ranking de produtos vendidos: {e}", exc_info=True)
            return "❌ Ocorreu um erro interno ao gerar o ranking."
