# integrations/commands/caixa_commands.py
from .base_command import BaseCommand
from typing import List

class CaixaCommand(BaseCommand):
    """Lida com subcomandos relacionados ao caixa."""
    def execute(self) -> str:
        if not self.args:
            return "Uso: /caixa [status|fechar|sangria|suprimento]"

        subcommand = self.args[0].lower()
        command_args = self.args[1:]

        if subcommand == 'status':
            return self._handle_caixa_status()
        elif subcommand == 'sangria':
            return self._handle_caixa_movimento('sangria', command_args)
        elif subcommand == 'suprimento':
            return self._handle_caixa_movimento('suprimento', command_args)
        elif subcommand == 'fechar':
            return self._handle_caixa_fechar()
        else:
            return f"Subcomando '/caixa {subcommand}' não reconhecido. Use '/ajuda' para ver as opções."

    def _handle_caixa_fechar(self) -> str:
        """Gera e envia um relatório de pré-fechamento do caixa."""
        try:
            session = self.db.get_current_cash_session()
            if not session:
                return "ℹ️ Não há caixa aberto para fechar."

            report = self.db.get_cash_session_report(session['id'])
            session_details = report['session']

            response = f"📄 *Relatório de Fechamento de Caixa*\n\n"
            response += f"👤 *Operador:* `{session_details['username']}`\n"
            response += f"⏰ *Abertura:* `{session_details['open_time'].strftime('%d/%m %H:%M')}`\n\n"
            response += f"💰 *Valor Inicial:* `R$ {session_details['initial_amount']:.2f}`\n"

            response += "\n💳 *Vendas por Pagamento:*\n"
            total_vendas = 0
            for sale in report['sales']:
                response += f"  - {sale['payment_method']}: `R$ {sale['total']:.2f}`\n"
                total_vendas += sale['total']
            response += f"  *Total de Vendas:* `R$ {total_vendas:.2f}`\n"

            if report['movements']:
                response += "\n↔️ *Movimentos de Caixa:*\n"
                for mov in report['movements']:
                    icon = "➖" if mov['type'] == 'sangria' else "➕"
                    response += f"  {icon} {mov['type'].capitalize()}: `R$ {mov['amount']:.2f}` ({mov['reason']})\n"
            
            response += "\n\n*Resumo Financeiro:*\n"
            response += f"  Saldo Inicial: `R$ {session_details['initial_amount']:.2f}`\n"
            
            cash_status = self.db.get_current_cash_status()
            response += f"  + Vendas (Dinheiro): `R$ {cash_status['cash_sales']:.2f}`\n"
            response += f"  + Suprimentos: `R$ {cash_status['suprimentos']:.2f}`\n"
            response += f"  - Sangrias: `R$ {cash_status['sangrias']:.2f}`\n"
            response += "  --------------------\n"
            response += f"💵 *Valor Esperado em Caixa:* `R$ {cash_status['current_balance']:.2f}`\n\n"
            response += "⚠️ *Atenção:* Este é um relatório preliminar. O caixa deve ser fechado fisicamente no sistema PDV para confirmar os valores."

            return response

        except Exception as e:
            self.logging.error(f"Erro ao gerar relatório de fechamento de caixa via comando: {e}", exc_info=True)
            return "❌ Ocorreu um erro interno ao gerar o relatório de fechamento."

    def _handle_caixa_movimento(self, tipo: str, args: List[str]) -> str:
        """Registra uma sangria ou suprimento no caixa."""
        try:
            if len(args) < 2:
                return f"Uso: /caixa {tipo} <valor> <motivo>"

            valor_str = args[0].replace(',', '.')
            valor = float(valor_str)
            motivo = " ".join(args[1:])

            session = self.db.get_current_cash_session()
            if not session:
                return "❌ Operação falhou: Não há caixa aberto."

            admin_user = self.db.get_user_by_username('admin')
            if not admin_user:
                return "❌ Operação falhou: Usuário 'admin' padrão não encontrado no sistema."

            session_id = session['id']
            user_id = admin_user['id']

            self.db.add_cash_movement(session_id, user_id, tipo, valor, motivo)
            
            tipo_str_upper = tipo.upper()
            return f"✅ *{tipo_str_upper}* de `R$ {valor:.2f}` registrada com sucesso no caixa."

        except ValueError:
            return "❌ Valor inválido. Por favor, insira um número (ex: 50.75)."
        except Exception as e:
            self.logging.error(f"Erro ao registrar {tipo} via comando: {e}", exc_info=True)
            return f"❌ Ocorreu um erro interno ao registrar a {tipo}."

    def _handle_caixa_status(self) -> str:
        """Retorna o status detalhado do caixa atual."""
        try:
            status = self.db.get_current_cash_status()
            if status.get('status') == 'FECHADO':
                return "ℹ️ O caixa está fechado no momento."

            open_time_str = status['open_time'].strftime('%d/%m/%Y às %H:%M')
            
            response = (
                f"📦 *Status do Caixa (Aberto)*\n\n"
                f"👤 *Operador:* `{status['username']}`\n"
                f"⏰ *Abertura:* `{open_time_str}`\n\n"
                f"💰 *Valor Inicial:* `R$ {status['initial_amount']:.2f}`\n"
                f"➕ *Suprimentos:* `R$ {status['suprimentos']:.2f}`\n"
                f"➖ *Sangrias:* `R$ {status['sangrias']:.2f}`\n"
                f"📈 *Vendas (Dinheiro):* `R$ {status['cash_sales']:.2f}`\n\n"
                f"💵 *Saldo Atual em Dinheiro:* `R$ {status['current_balance']:.2f}`"
            )
            return response
        except Exception as e:
            self.logging.error(f"Erro ao obter status do caixa via comando: {e}", exc_info=True)
            return "❌ Ocorreu um erro interno ao buscar o status do caixa."
