# integrations/commands/fiado_commands.py
from .base_command import BaseCommand
from typing import List
from decimal import Decimal
from datetime import datetime

try:
    from integrations.whatsapp_sales_notifications import get_whatsapp_sales_notifier
except ImportError:
    get_whatsapp_sales_notifier = None

class FiadoCommand(BaseCommand):
    """
    Comando principal para /fiado e /fiados.
    Atua como um roteador para os subcomandos de fiado.
    """
    def execute(self) -> str:
        if not self.args or self.args[0].lower() in ['listar', 'pendentes']:
            return self._handle_fiado_listar()

        subcommand = self.args[0].lower()
        command_args = self.args[1:]

        if subcommand == 'pago':
            return self._handle_fiado_pagar(command_args)
        elif subcommand == 'criar':
            return self._handle_fiado_criar(command_args)
        elif subcommand == 'detalhes':
            return self._handle_fiado_detalhes(command_args)
        elif subcommand == 'cancelar':
            return self._handle_fiado_cancelar(command_args)
        elif subcommand == 'editar':
            return self._handle_fiado_editar(command_args)
        else:
            # Se não for um subcomando conhecido, tenta buscar detalhes pelo nome/ID
            return self._handle_fiado_detalhes(self.args)

    def _handle_fiado_listar(self) -> str:
        """Lista os fiados pendentes."""
        try:
            sales = self.db.get_credit_sales(status_filter='pending')
            if not sales:
                return "✅ Nenhum fiado pendente encontrado."

            response = "📝 *Fiados Pendentes*\n\n"
            total_pending = Decimal('0')
            for sale in sales:
                total_pending += sale['balance_due']
                response += f"- *ID {sale['id']}*: `{sale['customer_name']}` - R$ {sale['balance_due']:.2f} (desde {datetime.fromisoformat(sale['created_date']).strftime('%d/%m')})\n"
            
            response += f"\n*Total Pendente:* `R$ {total_pending:.2f}`"
            return response
        except Exception as e:
            self.logging.error(f"Erro ao listar fiados via comando: {e}", exc_info=True)
            return "❌ Ocorreu um erro ao buscar a lista de fiados."

    def _handle_fiado_pagar(self, args: List[str]) -> str:
        """Marca um fiado como pago usando o ID."""
        if len(args) < 2:
            return "Uso: /fiado pago <ID do fiado> <valor> [método_pagamento]"

        try:
            credit_id = int(args[0])
            amount_paid = Decimal(args[1].replace(',', '.'))
            payment_method = args[2] if len(args) > 2 else 'Dinheiro'
            
            credit_sale = self.db.get_credit_sale_details(credit_id)
            if not credit_sale:
                return f"❌ Fiado com ID `{credit_id}` não encontrado."
            if credit_sale['status'] == 'paid' or credit_sale['status'] == 'cancelled':
                return f"ℹ️ O fiado de `{credit_sale['customer_name']}` (ID {credit_id}) já está com status '{credit_sale['status']}'."

            admin_user = self.db.get_user_by_username('admin')
            if not admin_user:
                return "❌ Operação falhou: Usuário 'admin' não encontrado."

            success, message = self.db.add_credit_payment(credit_id, amount_paid, admin_user['id'], payment_method)

            if success:
                if get_whatsapp_sales_notifier:
                    notifier = get_whatsapp_sales_notifier()
                    # notifier.notify_credit_paid(credit_id) # Ajustar notificador se necessário
                
                return f"✅ Pagamento de `R$ {amount_paid:.2f}` registrado para o fiado ID {credit_id}."
            else:
                return f"❌ Erro ao registrar pagamento: {message}"
        except ValueError:
            return "❌ ID ou valor inválido. Ex: /fiado pago 123 50,00"
        except Exception as e:
            self.logging.error(f"Erro ao pagar fiado via comando: {e}", exc_info=True)
            return "❌ Ocorreu um erro interno ao processar o pagamento."

    def _handle_fiado_criar(self, args: List[str]) -> str:
        """Cria um novo fiado."""
        try:
            # Extrair nome do cliente (pode ter espaços e estar entre aspas)
            customer_name_parts = []
            i = -1
            in_quotes = args[0].startswith('"')
            for i, part in enumerate(args):
                if in_quotes:
                    customer_name_parts.append(part.strip('"'))
                    if part.endswith('"'):
                        break
                else: # Se não começar com aspas, o nome é a primeira parte
                    customer_name_parts.append(part)
                    break
            customer_name = " ".join(customer_name_parts)
            remaining_args = args[i+1:]

            if len(remaining_args) < 1:
                return 'Uso: /fiado criar "Nome Completo" <valor> [observações]'

            amount = Decimal(remaining_args[0].replace(',', '.'))
            observations = " ".join(remaining_args[1:]) if len(remaining_args) > 1 else "Criado via WhatsApp"

            # Verificar se o usuário admin existe
            admin_user = self.db.get_user_by_username('admin')
            if not admin_user:
                return "❌ Operação falhou: Usuário 'admin' padrão não encontrado no sistema."

            # Buscar cliente pelo nome (simplificado, pega o primeiro que encontrar)
            customers = self.db.search_customers(customer_name)
            if not customers:
                return f"❌ Cliente '{customer_name}' não encontrado. Cadastre o cliente no sistema primeiro."
            customer_id = customers[0]['id']

            success, credit_id = self.db.create_credit_sale(customer_id, amount, admin_user['id'], observations=observations)

            if success:
                if get_whatsapp_sales_notifier:
                    notifier = get_whatsapp_sales_notifier()
                    notifier.notify_credit_created(credit_id)
                return f"✅ Novo fiado criado para `{customer_name}` no valor de `R$ {amount:.2f}` (ID: {credit_id})."
            else:
                return f"❌ Erro ao criar fiado: {credit_id}"
        except (ValueError, IndexError):
            return 'Uso inválido. Exemplo: /fiado criar "João Silva" 50,00'
        except Exception as e:
            self.logging.error(f"Erro ao criar fiado via comando: {e}", exc_info=True)
            return "❌ Ocorreu um erro interno ao criar o fiado."

    def _handle_fiado_cancelar(self, args: List[str]) -> str:
        """Cancela um fiado existente, marcando-o como 'cancelled'."""
        if len(args) != 1:
            return "Uso: /fiado cancelar <ID do fiado>"

        try:
            credit_id = int(args[0])
            admin_user = self.db.get_user_by_username('admin')
            if not admin_user:
                return "❌ Operação falhou: Usuário 'admin' não encontrado."

            sale_to_cancel = self.db.get_credit_sale_details(credit_id)
            if not sale_to_cancel:
                return f"❌ Fiado com ID `{credit_id}` não encontrado."

            if sale_to_cancel['total_paid'] > 0:
                return f"❌ Fiado ID `{credit_id}` não pode ser cancelado pois já possui pagamentos."

            success, message = self.db.update_credit_sale_status(credit_id, 'cancelled', admin_user['id'])

            if success:
                return f"🗑️ Fiado ID `{credit_id}` (Cliente: {sale_to_cancel['customer_name']}, Valor: R$ {sale_to_cancel['amount']:.2f}) foi cancelado."
            else:
                return f"❌ Erro ao cancelar fiado: {message}"
        except ValueError:
            return "❌ ID inválido. O ID deve ser um número."
        except Exception as e:
            self.logging.error(f"Erro ao cancelar fiado via comando: {e}", exc_info=True)
            return "❌ Ocorreu um erro interno ao cancelar o fiado."

    def _handle_fiado_editar(self, args: List[str]) -> str:
        """Edita o valor total de um fiado que não possui pagamentos."""
        if len(args) != 2:
            return "Uso: /fiado editar <ID do fiado> <novo valor>"

        try:
            credit_id = int(args[0])
            new_amount = Decimal(args[1].replace(',', '.'))

            if new_amount <= 0:
                return "❌ O valor deve ser maior que zero."

            # Verificar se o usuário admin existe
            admin_user = self.db.get_user_by_username('admin')
            if not admin_user:
                return "❌ Operação falhou: Usuário 'admin' não encontrado."

            # Buscar detalhes do fiado
            credit_sale = self.db.get_credit_sale_details(credit_id)
            if not credit_sale:
                return f"❌ Fiado com ID `{credit_id}` não encontrado."

            # Validar que não possui pagamentos
            if credit_sale['total_paid'] > 0:
                return f"❌ Fiado ID `{credit_id}` não pode ser editado pois já possui pagamentos (R$ {credit_sale['total_paid']:.2f})."

            # Validar status
            if credit_sale['status'] in ['paid', 'cancelled']:
                return f"❌ Fiado ID `{credit_id}` não pode ser editado pois está com status '{credit_sale['status']}'."

            # Atualizar o valor do fiado
            success, message = self.db.update_credit_sale_amount(credit_id, new_amount, admin_user['id'])

            if success:
                return f"✅ Valor do fiado ID `{credit_id}` (Cliente: {credit_sale['customer_name']}) atualizado de R$ {credit_sale['amount']:.2f} para R$ {new_amount:.2f}."
            else:
                return f"❌ Erro ao editar fiado: {message}"
        except ValueError:
            return "❌ ID ou valor inválido. Ex: /fiado editar 123 150,00"
        except Exception as e:
            self.logging.error(f"Erro ao editar fiado via comando: {e}", exc_info=True)
            return "❌ Ocorreu um erro interno ao editar o fiado."

    def _handle_fiado_detalhes(self, args: List[str]) -> str:
        """Mostra detalhes de um fiado por ID ou de todos os fiados de um cliente."""
        if not args:
            return "Uso: /fiado <ID do fiado> ou /fiado <nome do cliente>"

        search_term = " ".join(args)
        
        # Tenta interpretar como ID primeiro
        if len(args) == 1 and search_term.isdigit():
            try:
                credit_id = int(search_term)
                sale = self.db.get_credit_sale_details(credit_id)
                if not sale:
                    return f"🔎 Nenhum fiado encontrado com o ID `{credit_id}`."

                response = f"🧾 *Detalhes do Fiado ID {sale['id']}*\n\n"
                response += f"👤 *Cliente:* `{sale['customer_name']}`\n"
                response += f"💰 *Valor Total:* `R$ {sale['amount']:.2f}`\n"
                response += f"💵 *Valor Pago:* `R$ {sale['total_paid']:.2f}`\n"
                response += f"📈 *Saldo Devedor:* `R$ {sale['balance_due']:.2f}`\n"
                response += f"ℹ️ *Status:* `{sale['status']}`\n"
                response += f"🗓️ *Data:* {datetime.fromisoformat(sale['created_date']).strftime('%d/%m/%Y')}\n"
                
                if sale['payments']:
                    response += "\n*Pagamentos:*\n"
                    for p in sale['payments']:
                        response += f"- `R$ {p['amount_paid']:.2f}` em {datetime.fromisoformat(p['payment_date']).strftime('%d/%m')} ({p['payment_method']})\n"
                return response
            except Exception as e:
                self.logging.error(f"Erro ao buscar detalhes de fiado por ID: {e}", exc_info=True)
                return "❌ Ocorreu um erro ao buscar os detalhes."

        # Se não for ID, busca pelo nome do cliente
        try:
            all_sales = self.db.get_credit_sales() # Busca todos
            sales = [s for s in all_sales if search_term.lower() in s['customer_name'].lower()]
            
            if not sales:
                return f"🔎 Nenhum fiado encontrado para '{search_term}'."

            customer_name = sales[0]['customer_name'] # Pega o nome exato do primeiro resultado
            response = f"🧾 *Fiados de {customer_name}*\n\n"
            total_due = Decimal('0')
            
            # Filtra para mostrar apenas os do cliente exato e não pagos/cancelados
            customer_sales = [s for s in sales if s['customer_name'] == customer_name and s['status'] not in ('paid', 'cancelled')]

            if not customer_sales:
                 return f"✅ `{customer_name}` não possui fiados pendentes."

            for sale in customer_sales:
                total_due += sale['balance_due']
                response += f"- *ID {sale['id']}: R$ {sale['balance_due']:.2f}* (Total: R$ {sale['amount']:.2f})\n"
            
            response += f"\n*Total Devido:* `R$ {total_due:.2f}`"
            return response
        except Exception as e:
            self.logging.error(f"Erro ao buscar detalhes de fiado por nome: {e}", exc_info=True)
            return "❌ Ocorreu um erro ao buscar os detalhes."
