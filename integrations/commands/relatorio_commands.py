# integrations/commands/relatorio_commands.py
from .base_command import BaseCommand
from datetime import datetime, timedelta

class SalesReportCommand(BaseCommand):
    """Gera e retorna um relatório detalhado de vendas."""
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

            response = f"📊 *Relatório de Vendas ({date_str})*\n\n"

            # Métricas principais
            response += "💰 *Métricas Principais:*\n"
            response += f"  - Faturamento Total: `R$ {report['total_revenue']:.2f}`\n"
            response += f"  - Vendas Realizadas: `{report['total_sales_count']}`\n"
            response += f"  - Ticket Médio: `R$ {report['average_ticket']:.2f}`\n\n"

            # Vendas por forma de pagamento
            if report['payment_methods']:
                response += "💳 *Vendas por Pagamento:*\n"
                for pm in report['payment_methods']:
                    response += f"  - {pm['payment_method']}: `R$ {pm['total']:.2f}` ({pm['count']} vendas)\n"
                response += "\n"

            # Top produtos vendidos
            top_products = report.get('top_products', [])
            if top_products:
                response += "🏆 *Produtos Mais Vendidos:*\n"
                for i, product in enumerate(top_products[:5]):  # Top 5 produtos
                    emoji = "🥇" if i == 0 else "🥈" if i == 1 else "🥉" if i == 2 else f"{i+1}."
                    quantity_str = f"{product['quantity_sold']:.3f}".replace('.', ',')
                    response += f"  {emoji} `{product['description']}`\n"
                    response += f"      - Quantidade: `{quantity_str}` | Faturamento: `R$ {product['revenue']:.2f}`\n"
                response += "\n"

            # Informações de créditos/fiados
            credit_summary = self.db.get_monthly_credit_summary()
            credit_payments_today = self.db.get_credit_payments_by_period(start_date.isoformat(), end_date.isoformat())

            response += "💰 *Créditos (Fiados):*\n"
            response += f"  - Total a Receber: `R$ {credit_summary['total_due']:.2f}`\n"
            response += f"  - Recebido no Mês: `R$ {credit_summary['total_paid_month']:.2f}`\n"

            # Pagamentos de fiados no período
            total_credit_payments = sum(pm['total_paid'] for pm in credit_payments_today)
            if total_credit_payments > 0:
                response += f"  - Recebido no Período: `R$ {total_credit_payments:.2f}`\n"
            response += "\n"

            # Status do caixa
            cash_status = self.db.get_current_cash_status()
            response += "📦 *Caixa:*\n"
            if cash_status and cash_status['status'] == 'ABERTO':
                response += f"  - Status: `Aberto por {cash_status['username']}`\n"
                response += f"  - Saldo em Dinheiro: `R$ {cash_status['current_balance']:.2f}`\n"
                if cash_status.get('suprimentos', 0) > 0:
                    response += f"  - Suprimentos: `R$ {cash_status['suprimentos']:.2f}`\n"
                if cash_status.get('sangrias', 0) > 0:
                    response += f"  - Sangrias: `R$ {cash_status['sangrias']:.2f}`\n"
            else:
                response += "  - Status: `Fechado`\n"

            # Alertas de estoque baixo (se for período atual)
            if start_date <= today <= end_date:
                stock_report = self.db.get_stock_report()
                if stock_report['low_stock_items']:
                    response += "\n\n⚠️ *Alertas de Estoque Baixo:*\n"
                    for item in stock_report['low_stock_items'][:3]:  # Máximo 3 itens
                        response += f"  - {item['description']}: `{item['stock']:.3f}`\n"
                    if len(stock_report['low_stock_items']) > 3:
                        response += f"  ... e mais {len(stock_report['low_stock_items']) - 3} itens\n"

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

            # Informações de crédito/fiados
            credit_summary = self.db.get_monthly_credit_summary()
            credit_payments_today = self.db.get_credit_payments_by_period(today_str, today_str)

            # Alertas de estoque baixo
            stock_report = self.db.get_stock_report()

            # Últimas vendas
            latest_sales = self.db.get_latest_sales(3)

            top_product = report['top_products'][0]['description'] if report['top_products'] else "N/A"

            response = f"📈 *Dashboard do Dia ({datetime.now().strftime('%d/%m/%Y')})*\n\n"

            # Seção de Vendas
            response += "📊 *Vendas:*\n"
            response += f"  💰 Faturamento Total: `R$ {report['total_revenue']:.2f}`\n"
            response += f"  🛒 Vendas Realizadas: `{report['total_sales_count']}`\n"
            response += f"  📈 Ticket Médio: `R$ {report['average_ticket']:.2f}`\n"
            response += f"  🏆 Produto Mais Vendido: `{top_product}`\n\n"

            # Vendas por forma de pagamento
            if report['payment_methods']:
                response += "💳 *Vendas por Pagamento:*\n"
                for pm in report['payment_methods']:
                    response += f"  - {pm['payment_method']}: `R$ {pm['total']:.2f}` ({pm['count']} vendas)\n"
                response += "\n"

            # Seção de Créditos/Fiados
            response += "💰 *Créditos (Fiados):*\n"
            response += f"  📥 Total a Receber: `R$ {credit_summary['total_due']:.2f}`\n"
            response += f"  📤 Recebido no Mês: `R$ {credit_summary['total_paid_month']:.2f}`\n"

            # Pagamentos de fiados hoje
            total_credit_payments_today = sum(pm['total_paid'] for pm in credit_payments_today)
            if total_credit_payments_today > 0:
                response += f"  ✅ Recebido Hoje: `R$ {total_credit_payments_today:.2f}`\n"
            response += "\n"

            # Seção de Caixa
            response += "📦 *Caixa:*\n"
            if cash_status.get('status') == 'ABERTO':
                response += f"  🔓 Status: `Aberto por {cash_status['username']}`\n"
                response += f"  💵 Saldo em Dinheiro: `R$ {cash_status['current_balance']:.2f}`\n"
                if cash_status.get('suprimentos', 0) > 0:
                    response += f"  ➕ Suprimentos: `R$ {cash_status['suprimentos']:.2f}`\n"
                if cash_status.get('sangrias', 0) > 0:
                    response += f"  ➖ Sangrias: `R$ {cash_status['sangrias']:.2f}`\n"
            else:
                response += "  🔒 Status: `Fechado`\n"
            response += "\n"

            # Alertas de Estoque Baixo
            if stock_report['low_stock_items']:
                response += "⚠️ *Alertas de Estoque:*\n"
                for item in stock_report['low_stock_items'][:5]:  # Máximo 5 itens
                    response += f"  - {item['description']}: `{item['stock']:.3f}`\n"
                if len(stock_report['low_stock_items']) > 5:
                    response += f"  ... e mais {len(stock_report['low_stock_items']) - 5} itens\n"
                response += "\n"

            # Últimas Vendas
            if latest_sales:
                response += "🕒 *Últimas Vendas:*\n"
                for sale in latest_sales:
                    time_str = sale['sale_date'].strftime('%H:%M')
                    response += f"  - {time_str} | {sale['username']} | `R$ {sale['total_amount']:.2f}`\n"
                response += "\n"

            # Remover última quebra de linha extra
            response = response.rstrip() + "\n\n_Dashboard gerado automaticamente_"

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
