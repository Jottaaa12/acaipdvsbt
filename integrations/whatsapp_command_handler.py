# Conteúdo para integrations/whatsapp_command_handler.py
import logging
from datetime import datetime, timedelta
from decimal import Decimal
import database as db
from .whatsapp_config import get_whatsapp_config
import os
import json
from typing import List, Dict, Any

# O CommandHandler agora é uma classe puramente de processamento, com cache de permissões.
class CommandHandler:
    def __init__(self):
        self.config = get_whatsapp_config()
        self.authorized_managers = []
        self.update_authorized_managers()  # Carga inicial
        
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

    def process_command(self, command_data: dict, manager) -> List[tuple[str, str]]:
        """
        Processa um comando, registra a auditoria e retorna uma LISTA de tuplas de resposta.
        Recebe a instância do manager para acessar métodos de status e logging.
        Retorna: [(response_text, recipient_phone)] ou []
        """
        sender_phone_raw = command_data.get('sender')
        command_text = command_data.get('text', '').strip()

        # Normaliza o número do remetente antes de verificar
        validation = self.config.validate_phone(sender_phone_raw)
        if not validation['valid']:
            logging.warning(f"Número de remetente com formato inválido foi ignorado: {sender_phone_raw}")
            return []
        
        sender_phone = validation['normalized']

        # A verificação agora usa a lista normalizada em cache.
        if not sender_phone or sender_phone not in self.authorized_managers:
            logging.warning(f"Comando de número não autorizado foi ignorado: {sender_phone} (Lista de autorizados: {self.authorized_managers})")
            # Log de tentativa de comando não autorizado
            manager.logger.log_command(sender=sender_phone, command=command_text, success=False, response_preview="Acesso negado")
            return []

        parts = command_text.split()
        command = parts[0].lower()
        args = parts[1:]

        command_map = {
            '/ajuda': self._handle_help,
            '/notificacoes': self._handle_notifications,
            '/vendas': self._handle_sales_report,
            '/relatorio': self._handle_sales_report,  # Alias para /vendas
            '/status': self._handle_status,
            '/logs': self._handle_logs,
            '/caixa': self._handle_caixa,
            '/produto': self._handle_produto,
            '/estoque': self._handle_estoque,
            '/backup': self._handle_backup,
            '/gerente': self._handle_gerente,
            '/dashboard': self._handle_dashboard,
            '/produtos_vendidos': self._handle_produtos_vendidos,
            '/sistema': self._handle_sistema,
            '/fiado': self._handle_fiado, # Novo comando
            '/fiados': self._handle_fiado, # Alias
        }

        handler_func = command_map.get(command)
        if handler_func:
            # Passa o manager para handlers que precisam dele
            if command in ['/status', '/logs', '/gerente', '/sistema']:
                response = handler_func(args, manager=manager)
            else:
                response = handler_func(args)
            # Log de comando bem-sucedido
            manager.logger.log_command(sender=sender_phone, command=command_text, success=True, response_preview=response)
        else:
            response = f"Comando '{command}' não reconhecido. Digite '/ajuda' para ver a lista de comandos."
            # Log de comando não reconhecido
            manager.logger.log_command(sender=sender_phone, command=command_text, success=False, response_preview="Comando não reconhecido")

        if response:
            return [(response, sender_phone)]
        
        return []

    def _handle_fiado(self, args: list):
        """Lida com subcomandos para o sistema de fiado."""
        if not args or args[0].lower() in ['listar', 'pendentes']:
            return self._handle_fiado_listar()

        subcommand = args[0].lower()
        command_args = args[1:]

        if subcommand == 'pago':
            return self._handle_fiado_pagar(command_args)
        elif subcommand == 'criar':
            return self._handle_fiado_criar(command_args)
        elif subcommand == 'detalhes':
            return self._handle_fiado_detalhes(command_args)
        elif subcommand == 'editar':
            return self._handle_fiado_editar(command_args)
        elif subcommand == 'excluir':
            return self._handle_fiado_excluir(command_args)
        else:
            # Se nenhum subcomando conhecido, assume que é uma busca por nome
            return self._handle_fiado_detalhes(args)


    def _handle_help(self, args):
        """Retorna a mensagem de ajuda com os comandos disponíveis."""
        return (
            "🤖 *Assistente Virtual PDV* 🤖\n\n"
            "Aqui estão os comandos que você pode usar:\n\n"
            "💳 *FIADOS (CONTAS A RECEBER)*\n"
            "  `*/fiados`* - Lista os fiados pendentes (com ID).\n"
            "  `*/fiado pago <ID do fiado>`* - Marca um fiado como pago.\n"
            "  `*/fiado detalhes <nome do cliente>`* - Mostra detalhes dos fiados de um cliente.\n"
            "  `*/fiado criar \"Nome Cliente\" <valor>`* - Cria um novo fiado.\n"
            "  `*/fiado editar <ID> <novo valor>`* - Edita o valor de um fiado.\n"
            "  `*/fiado excluir <ID>`* - Exclui um fiado.\n\n"
            "📈 *DASHBOARD*\n"
            "  `*/dashboard`* - Resumo completo do dia.\n\n"
            "📊 *RELATÓRIOS*\n"
            "  `*/vendas <período>`* - Vendas do período (hoje, ontem, 7dias, etc.).\n"
            "  `*/produtos_vendidos <período>`* - Ranking de produtos mais vendidos.\n\n"
            "📦 *CAIXA*\n"
            "  `*/caixa status`* - Status detalhado do caixa atual.\n"
            "  `*/caixa fechar`* - Relatório de pré-fechamento.\n"
            "  `*/caixa sangria <valor> <motivo>`* - Registrar sangria.\n"
            "  `*/caixa suprimento <valor> <motivo>`* - Registrar suprimento.\n\n"
            "📝 *PRODUTOS E ESTOQUE*\n"
            "  `*/produto consultar <nome/cód>`* - Detalhes de um produto.\n"
            "  `*/produto alterar_preco <cód> <preço>`* - Altera o preço.\n"
            "  `*/estoque baixo`* - Lista produtos com estoque baixo.\n"
            "  `*/estoque ajustar <cód> <qtd>`* - Ajusta o estoque.\n\n"
            "⚙️ *ADMINISTRAÇÃO*\n"
            "  `*/gerente listar`* - Lista os gerentes.\n"
            "  `*/gerente adicionar <número>`* - Adiciona um gerente.\n"
            "  `*/gerente remover <número>`* - Remove um gerente.\n"
            "  `*/notificacoes <on/off>`* - Ativa/desativa notificações.\n\n"
            "🛠️ *SISTEMA*\n"
            "  `*/status`* - Saúde da integração WhatsApp.\n"
            "  `*/logs <nível> [linhas]`* - Exibe logs do sistema.\n"
            "  `*/backup`* - Inicia o backup do banco de dados.\n"
            "  `*/sistema limpar_sessao`* - Reinicia a conexão com o WhatsApp.\n\n"
            "ℹ️ Digite um comando para começar!"
        )

    def _handle_fiado_listar(self):
        """Lista os fiados pendentes."""
        try:
            sales = db.get_credit_sales(status_filter='pending')
            if not sales:
                return "✅ Nenhum fiado pendente encontrado."

            response = "📝 *Fiados Pendentes*\n\n"
            total_pending = Decimal('0')
            for sale in sales:
                total_pending += sale['amount']
                response += f"- *ID {sale['id']}*: `{sale['customer_name']}` - R$ {sale['amount']:.2f} (desde {datetime.fromisoformat(sale['created_date']).strftime('%d/%m')})\n"
            
            response += f"\n*Total Pendente:* `R$ {total_pending:.2f}`"
            return response
        except Exception as e:
            logging.error(f"Erro ao listar fiados via comando: {e}", exc_info=True)
            return "❌ Ocorreu um erro ao buscar a lista de fiados."

    def _handle_fiado_pagar(self, args: list):
        """Marca um fiado como pago usando o ID."""
        if not args:
            return "Uso: /fiado pago <ID do fiado>"

        try:
            credit_id = int(args[0])
            
            credit_sale = db.get_credit_sale_by_id(credit_id)
            if not credit_sale:
                return f"❌ Fiado com ID `{credit_id}` não encontrado."
            if credit_sale['status'] != 'pending':
                return f"ℹ️ O fiado de `{credit_sale['customer_name']}` (ID {credit_id}) já está com status '{credit_sale['status']}'."

            admin_user = db.get_user_by_username('admin')
            success, message = db.mark_credit_as_paid(credit_id, admin_user['id'])

            if success:
                from .whatsapp_sales_notifications import get_whatsapp_sales_notifier
                notifier = get_whatsapp_sales_notifier()
                paid_sale_data = db.get_credit_sale_by_id(credit_id)
                if paid_sale_data:
                    notifier.notify_credit_paid(paid_sale_data)
                
                return f"✅ Fiado de `R$ {credit_sale['amount']:.2f}` para `{credit_sale['customer_name']}` (ID {credit_id}) foi marcado como pago."
            else:
                return f"❌ Erro ao marcar fiado como pago: {message}"
        except ValueError:
            return "❌ ID inválido. O ID do fiado deve ser um número."
        except Exception as e:
            logging.error(f"Erro ao pagar fiado via comando: {e}", exc_info=True)
            return "❌ Ocorreu um erro interno ao processar o pagamento."

    def _handle_fiado_criar(self, args: list):
        """Cria um novo fiado."""
        try:
            # Extrai o nome do cliente (pode estar entre aspas)
            if args[0].startswith('"'):
                customer_name_parts = []
                i = -1
                for i, part in enumerate(args):
                    customer_name_parts.append(part.strip('"'))
                    if part.endswith('"'):
                        break
                customer_name = " ".join(customer_name_parts)
                remaining_args = args[i+1:]
            else:
                customer_name = args[0]
                remaining_args = args[1:]

            if len(remaining_args) < 1:
                return 'Uso: /fiado criar "Nome Completo" <valor> [data_vencimento AAAA-MM-DD]'

            amount = float(remaining_args[0].replace(',', '.'))
            due_date = remaining_args[1] if len(remaining_args) > 1 else None

            admin_user = db.get_user_by_username('admin')
            success, credit_id = db.create_credit_sale(customer_name, amount, due_date, "Criado via WhatsApp", admin_user['id'])

            if success:
                from .whatsapp_sales_notifications import get_whatsapp_sales_notifier
                notifier = get_whatsapp_sales_notifier()
                new_sale_data = db.get_credit_sale_by_id(credit_id)
                if new_sale_data:
                    notifier.notify_credit_created(new_sale_data)
                return f"✅ Novo fiado criado para `{customer_name}` no valor de `R$ {amount:.2f}` (ID: {credit_id})."
            else:
                return f"❌ Erro ao criar fiado: {credit_id}"
        except (ValueError, IndexError):
            return 'Uso inválido. Exemplo: /fiado criar "João Silva" 50,00'
        except Exception as e:
            logging.error(f"Erro ao criar fiado via comando: {e}", exc_info=True)
            return "❌ Ocorreu um erro interno ao criar o fiado."

    def _handle_fiado_editar(self, args: list):
        """Edita o valor de um fiado existente."""
        if len(args) != 2:
            return "Uso: /fiado editar <ID do fiado> <novo valor>"

        try:
            credit_id = int(args[0])
            new_amount = float(args[1].replace(',', '.'))

            admin_user = db.get_user_by_username('admin')
            if not admin_user:
                return "❌ Operação falhou: Usuário 'admin' não encontrado."

            old_sale = db.get_credit_sale_by_id(credit_id)
            if not old_sale:
                return f"❌ Fiado com ID `{credit_id}` não encontrado."

            success, message = db.update_credit_sale(
                credit_id=credit_id,
                customer_name=old_sale['customer_name'],
                amount=new_amount,
                due_date=old_sale['due_date'],
                observations=old_sale['observations'],
                user_id=admin_user['id']
            )

            if success:
                return f"✅ Valor do fiado ID `{credit_id}` alterado de `R$ {old_sale['amount']:.2f}` para `R$ {new_amount:.2f}`."
            else:
                return f"❌ Erro ao editar fiado: {message}"
        except ValueError:
            return "❌ Uso inválido. Ex: /fiado editar 123 50,00"
        except Exception as e:
            logging.error(f"Erro ao editar fiado via comando: {e}", exc_info=True)
            return "❌ Ocorreu um erro interno ao editar o fiado."

    def _handle_fiado_excluir(self, args: list):
        """Exclui um fiado existente."""
        if len(args) != 1:
            return "Uso: /fiado excluir <ID do fiado>"

        try:
            credit_id = int(args[0])
            admin_user = db.get_user_by_username('admin')
            if not admin_user:
                return "❌ Operação falhou: Usuário 'admin' não encontrado."

            sale_to_delete = db.get_credit_sale_by_id(credit_id)
            if not sale_to_delete:
                return f"❌ Fiado com ID `{credit_id}` não encontrado."

            success, message = db.delete_credit_sale(credit_id, admin_user['id'])

            if success:
                return f"🗑️ Fiado ID `{credit_id}` (Cliente: {sale_to_delete['customer_name']}, Valor: R$ {sale_to_delete['amount']:.2f}) foi excluído."
            else:
                return f"❌ Erro ao excluir fiado: {message}"
        except ValueError:
            return "❌ ID inválido. O ID deve ser um número."
        except Exception as e:
            logging.error(f"Erro ao excluir fiado via comando: {e}", exc_info=True)
            return "❌ Ocorreu um erro interno ao excluir o fiado."

    def _handle_fiado_detalhes(self, args: list):
        """Mostra detalhes dos fiados de um cliente."""
        if not args:
            return "Uso: /fiado detalhes <nome do cliente>"

        customer_name = " ".join(args)
        try:
            all_sales = db.get_credit_sales()
            sales = [s for s in all_sales if s['customer_name'].lower() == customer_name.lower()]
            if not sales:
                return f"🔎 Nenhum fiado encontrado para '{customer_name}'."

            response = f"🧾 *Detalhes de Fiados para {customer_name}*\n\n"
            total_due = Decimal('0')
            for sale in sales:
                status_icon = "✅" if sale['status'] == 'paid' else "📝" if sale['status'] == 'pending' else "❌"
                response += f"{status_icon} *ID {sale['id']}: R$ {sale['amount']:.2f}* ({sale['status']})\n"
                response += f"   - Data: {datetime.fromisoformat(sale['created_date']).strftime('%d/%m/%Y')}\n"
                if sale['status'] == 'pending':
                    total_due += sale['amount']
            
            response += f"\n*Total Devido:* `R$ {total_due:.2f}`"
            return response
        except Exception as e:
            logging.error(f"Erro ao buscar detalhes de fiado via comando: {e}", exc_info=True)
            return "❌ Ocorreu um erro ao buscar os detalhes."

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
            
            # Adiciona o status do caixa atual
            cash_status = db.get_current_cash_status()
            if cash_status and cash_status['status'] == 'ABERTO':
                response += f"\n\n📦 *Caixa Atual (Aberto por {cash_status['username']})*\n"
                response += f"  - Saldo em Dinheiro: `R$ {cash_status['current_balance']:.2f}`"

            return response
        except ValueError:
            logging.warning(f"Comando de relatório de vendas com formato de data inválido: {args}")
            return "🗓️ Formato de data inválido. Use AAAA-MM-DD, por exemplo: `/relatorio 2025-10-01 2025-10-05`."
        except Exception as e:
            logging.error(f"Erro inesperado ao gerar relatório de vendas via comando: {e}", exc_info=True)
            return "❌ Ocorreu um erro interno ao gerar o relatório. A equipe de suporte foi notificada."

    def _handle_caixa(self, args):
        """Lida com subcomandos relacionados ao caixa."""
        if not args:
            return "Uso: /caixa [status|fechar|sangria|suprimento]"

        subcommand = args[0].lower()
        command_args = args[1:]

        if subcommand == 'status':
            return self._handle_caixa_status()
        elif subcommand == 'sangria':
            return self._handle_caixa_movimento('sangria', command_args)
        elif subcommand == 'suprimento':
            return self._handle_caixa_movimento('suprimento', command_args)
        elif subcommand == 'fechar':
            return self._handle_caixa_fechar()
        # Futuros subcomandos serão adicionados aqui
        else:
            return f"Subcomando '/caixa {subcommand}' não reconhecido. Use '/ajuda' para ver as opções."

    def _handle_caixa_fechar(self):
        """Gera e envia um relatório de pré-fechamento do caixa."""
        try:
            session = db.get_current_cash_session()
            if not session:
                return "ℹ️ Não há caixa aberto para fechar."

            report = db.get_cash_session_report(session['id'])
            session_details = report['session']

            response = f"📄 *Relatório de Fechamento de Caixa*\n\n"
            response += f"👤 *Operador:* `{session_details['username']}`\n"
            response += f"⏰ *Abertura:* `{session_details['open_time'].strftime('%d/%m %H:%M')}`\n\n"
            response += f"💰 *Valor Inicial:* `R$ {session_details['initial_amount']:.2f}`\n"

            # Vendas por método de pagamento
            response += "\n💳 *Vendas por Pagamento:*\n"
            total_vendas = 0
            for sale in report['sales']:
                response += f"  - {sale['payment_method']}: `R$ {sale['total']:.2f}`\n"
                total_vendas += sale['total']
            response += f"  *Total de Vendas:* `R$ {total_vendas:.2f}`\n"

            # Movimentos de caixa
            if report['movements']:
                response += "\n↔️ *Movimentos de Caixa:*\n"
                for mov in report['movements']:
                    icon = "➖" if mov['type'] == 'sangria' else "➕"
                    response += f"  {icon} {mov['type'].capitalize()}: `R$ {mov['amount']:.2f}` ({mov['reason']})\n"
            
            # Resumo final
            response += "\n\n*Resumo Financeiro:*\n"
            response += f"  Saldo Inicial: `R$ {session_details['initial_amount']:.2f}`\n"
            
            cash_status = db.get_current_cash_status()
            response += f"  + Vendas (Dinheiro): `R$ {cash_status['cash_sales']:.2f}`\n"
            response += f"  + Suprimentos: `R$ {cash_status['suprimentos']:.2f}`\n"
            response += f"  - Sangrias: `R$ {cash_status['sangrias']:.2f}`\n"
            response += "  --------------------\n"
            response += f"💵 *Valor Esperado em Caixa:* `R$ {cash_status['current_balance']:.2f}`\n\n"
            response += "⚠️ *Atenção:* Este é um relatório preliminar. O caixa deve ser fechado fisicamente no sistema PDV para confirmar os valores."

            return response

        except Exception as e:
            logging.error(f"Erro ao gerar relatório de fechamento de caixa via comando: {e}", exc_info=True)
            return "❌ Ocorreu um erro interno ao gerar o relatório de fechamento."

    def _handle_produto(self, args: list):
        """Lida com subcomandos relacionados a produtos."""
        if not args:
            return "Uso: /produto [consultar|alterar_preco] <argumentos>"

        subcommand = args[0].lower()
        command_args = args[1:]

        if subcommand == 'consultar':
            return self._handle_produto_consultar(command_args)
        elif subcommand == 'alterar_preco':
            return self._handle_produto_alterar_preco(command_args)
        else:
            # Para manter a compatibilidade com o uso anterior de "/produto <nome>"
            return self._handle_produto_consultar(args)

    def _handle_produto_consultar(self, args: list):
        """Busca e retorna informações de um produto."""
        if not args:
            return "Uso: /produto consultar <código de barras ou nome>"

        identifier = " ".join(args)
        try:
            product = db.get_product_by_barcode_or_name(identifier)

            if not product:
                return f"🔎 Nenhum produto encontrado com o identificador '{identifier}'."

            stock_str = f"{product['stock']:.3f}".replace('.', ',')
            sale_type_str = "Unidade" if product['sale_type'] == 'unit' else "Peso"

            response = (
                f"📦 *Detalhes do Produto*\n\n"
                f"📝 *Descrição:* `{product['description']}`\n"
                f"🔢 *Cód. Barras:* `{product['barcode'] or 'N/A'}`\n"
                f"💰 *Preço:* `R$ {product['price']:.2f}`\n"
                f"🗃️ *Estoque:* `{stock_str}`\n"
                f"⚖️ *Vendido por:* `{sale_type_str}`\n"
                f"📂 *Grupo:* `{product['group_name'] or 'Nenhum'}`"
            )
            return response

        except Exception as e:
            logging.error(f"Erro ao buscar produto via comando: {e}", exc_info=True)
            return "❌ Ocorreu um erro interno ao buscar o produto."

    def _handle_produto_alterar_preco(self, args: list):
        """Altera o preço de um produto."""
        try:
            if len(args) != 2:
                return "Uso: /produto alterar_preco <código_de_barras> <novo_preço>"

            barcode = args[0]
            new_price_str = args[1].replace(',', '.')
            new_price = float(new_price_str)

            old_product = db.get_product_by_barcode(barcode)
            if not old_product:
                return f"❌ Produto com código de barras '{barcode}' não encontrado."

            success, message = db.update_product_price(barcode, new_price)

            if success:
                return (
                    f"✅ Preço do produto `{old_product['description']}` alterado com sucesso!\n\n"
                    f"Preço anterior: `R$ {old_product['price']:.2f}`\n"
                    f"Novo preço: `R$ {new_price:.2f}`"
                )
            else:
                return f"❌ Falha ao alterar o preço: {message}"

        except ValueError:
            return "❌ Preço inválido. Por favor, insira um número (ex: 25.99)."
        except Exception as e:
            logging.error(f"Erro ao alterar preço via comando: {e}", exc_info=True)
            return "❌ Ocorreu um erro interno ao alterar o preço."

    def _handle_backup(self, args: list):
        """Inicia a rotina de backup do banco de dados."""
        try:
            success, message = db.create_backup()
            if success:
                return f"✅ Backup do banco de dados criado com sucesso em: `{message}`"
            else:
                return f"❌ Falha ao criar backup: {message}"
        except Exception as e:
            logging.error(f"Erro ao iniciar backup via comando: {e}", exc_info=True)
            return "❌ Ocorreu um erro interno ao tentar criar o backup."

    def _handle_dashboard(self, args: list):
        """Retorna um dashboard com o resumo do dia."""
        try:
            today_str = datetime.now().date().isoformat()
            report = db.get_sales_report(today_str, today_str)
            cash_status = db.get_current_cash_status()

            top_product = report['top_products'][0]['description'] if report['top_products'] else "N/A"

            response = f"📈 *Dashboard do Dia ({datetime.now().strftime('%d/%m/%Y')})*\n\n"
            
            # Resumo de Vendas
            response += "📊 *Vendas:*\n"
            response += f"  - Faturamento Total: `R$ {report['total_revenue']:.2f}`\n"
            response += f"  - Vendas Realizadas: `{report['total_sales_count']}`\n"
            response += f"  - Ticket Médio: `R$ {report['average_ticket']:.2f}`\n"
            response += f"  - Produto Mais Vendido: `{top_product}`\n\n"

            # Resumo do Caixa
            response += "📦 *Caixa:*\n"
            if cash_status.get('status') == 'ABERTO':
                response += f"  - Status: `Aberto por {cash_status['username']}`\n"
                response += f"  - Saldo em Dinheiro: `R$ {cash_status['current_balance']:.2f}`\n"
            else:
                response += "  - Status: `Fechado`\n"

            return response

        except Exception as e:
            logging.error(f"Erro ao gerar dashboard via comando: {e}", exc_info=True)
            return "❌ Ocorreu um erro interno ao gerar o dashboard."

    def _handle_produtos_vendidos(self, args: list):
        """Retorna um ranking dos produtos mais vendidos em um período."""
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
                return "Formato do período inválido. Use 'hoje', 'ontem', '7dias' ou um intervalo de datas."

            report = db.get_sales_report(start_date.isoformat(), end_date.isoformat())
            top_products = report.get('top_products', [])

            if not top_products:
                return "ℹ️ Nenhuma venda de produto registrada no período."

            date_str = f"de {start_date.strftime('%d/%m')} a {end_date.strftime('%d/%m')}" if start_date != end_date else f"em {start_date.strftime('%d/%m/%Y')}"
            response = f"🏆 *Produtos Mais Vendidos ({date_str})*\n\n"
            
            for i, product in enumerate(top_products[:10]):  # Limita aos 10 primeiros
                emoji = "🥇" if i == 0 else "🥈" if i == 1 else "🥉" if i == 2 else f"{i+1}."
                quantity_str = f"{product['quantity_sold']:.3f}".replace('.', ',')
                response += f"{emoji} `{product['description']}`\n"
                response += f"    - Quantidade: `{quantity_str}`\n"
                response += f"    - Faturamento: `R$ {product['revenue']:.2f}`\n"

            return response.strip()

        except ValueError:
            return "🗓️ Formato de data inválido. Use AAAA-MM-DD."
        except Exception as e:
            logging.error(f"Erro ao gerar ranking de produtos vendidos: {e}", exc_info=True)
            return "❌ Ocorreu um erro interno ao gerar o ranking."

    def _handle_sistema(self, args: list, manager):
        """Lida com comandos de sistema."""
        if not args:
            return "Uso: /sistema [limpar_sessao]"

        subcommand = args[0].lower()
        if subcommand == 'limpar_sessao':
            try:
                manager.disconnect(cleanup_session=True)
                return "✅ Sessão do WhatsApp limpa. Por favor, reinicie a conexão no PDV para gerar um novo QR Code."
            except Exception as e:
                logging.error(f"Erro ao limpar sessão via comando: {e}", exc_info=True)
                return "❌ Ocorreu um erro ao tentar limpar a sessão."
        else:
            return f"Subcomando '/sistema {subcommand}' não reconhecido."

    def _handle_gerente(self, args: list, manager):
        """Lida com subcomandos de gerenciamento de gerentes."""
        if not args:
            return "Uso: /gerente [listar|adicionar|remover]"

        subcommand = args[0].lower()
        command_args = args[1:]

        if subcommand == 'listar':
            return self._handle_gerente_listar()
        elif subcommand == 'adicionar':
            return self._handle_gerente_adicionar(command_args, manager)
        elif subcommand == 'remover':
            return self._handle_gerente_remover(command_args, manager)
        else:
            return f"Subcomando '/gerente {subcommand}' não reconhecido."

    def _handle_gerente_listar(self):
        """Lista os gerentes autorizados."""
        numbers_str = db.load_setting('whatsapp_manager_numbers', '')
        if not numbers_str:
            return "ℹ️ Nenhum gerente cadastrado."
        
        numbers = [num.strip() for num in numbers_str.split(',')]
        response = "👨‍💼 *Gerentes Autorizados*\n\n"
        for num in numbers:
            response += f"- `{num}`\n"
        return response

    def _handle_gerente_adicionar(self, args: list, manager):
        """Adiciona um novo gerente."""
        if len(args) != 1:
            return "Uso: /gerente adicionar <número_telefone>"
        
        new_number = args[0]
        validation = self.config.validate_phone(new_number)
        if not validation['valid']:
            return f"❌ Número '{new_number}' inválido."

        normalized_number = validation['normalized']
        
        numbers_str = db.load_setting('whatsapp_manager_numbers', '')
        numbers = [num.strip() for num in numbers_str.split(',') if num.strip()]

        if normalized_number in numbers:
            return f"ℹ️ O número `{normalized_number}` já é um gerente."

        numbers.append(normalized_number)
        db.save_setting('whatsapp_manager_numbers', ",".join(numbers))
        manager.update_authorized_users()  # Atualiza em tempo real

        return f"✅ Novo gerente `{normalized_number}` adicionado com sucesso."

    def _handle_gerente_remover(self, args: list, manager):
        """Remove um gerente."""
        if len(args) != 1:
            return "Uso: /gerente remover <número_telefone>"

        number_to_remove = args[0]
        validation = self.config.validate_phone(number_to_remove)
        if not validation['valid']:
            return f"❌ Número '{number_to_remove}' inválido."
        
        normalized_number = validation['normalized']

        numbers_str = db.load_setting('whatsapp_manager_numbers', '')
        numbers = [num.strip() for num in numbers_str.split(',') if num.strip()]

        if normalized_number not in numbers:
            return f"ℹ️ O número `{normalized_number}` não foi encontrado na lista de gerentes."

        numbers.remove(normalized_number)
        db.save_setting('whatsapp_manager_numbers', ",".join(numbers))
        manager.update_authorized_users()  # Atualiza em tempo real

        return f"✅ Gerente `{normalized_number}` removido com sucesso."

    def _handle_estoque(self, args: list):
        """Lida com subcomandos relacionados ao estoque."""
        if not args:
            return "Uso: /estoque [grupos|ver|add|baixa|ajustar|baixo]"

        subcommand = args[0].lower()
        command_args = args[1:]

        if subcommand == 'grupos':
            return self._handle_estoque_grupos()
        elif subcommand == 'ver':
            return self._handle_estoque_ver()
        elif subcommand == 'add':
            return self._handle_estoque_add(command_args)
        elif subcommand == 'baixa':
            return self._handle_estoque_baixa(command_args)
        elif subcommand == 'ajustar':
            return self._handle_estoque_ajustar(command_args)
        elif subcommand == 'baixo':
            return self._handle_estoque_baixo()
        else:
            return f"Subcomando '/estoque {subcommand}' não reconhecido. Use '/ajuda' para ver as opções."

    def _handle_estoque_grupos(self):
        """Lista os grupos de estoque."""
        try:
            grupos = db.get_all_groups()
            if not grupos:
                return "Nenhum grupo de estoque encontrado."
            
            response = "📂 *Grupos de Estoque:*\n"
            for grupo in grupos:
                response += f"- {grupo['nome']}\n"
            return response
        except Exception as e:
            logging.error(f"Erro ao listar grupos de estoque: {e}", exc_info=True)
            return "❌ Erro ao buscar grupos de estoque."

    def _handle_estoque_ver(self):
        """Lista todos os itens de estoque, agrupados."""
        try:
            itens = db.get_stock_report()['stock_levels']
            if not itens:
                return "Nenhum item no estoque."

            response = "📦 *Itens em Estoque:*\n"
            current_group = None
            for item in itens:
                if item['group_name'] != current_group:
                    current_group = item['group_name']
                    response += f"\n--- *{current_group}* ---\n"
                response += f"({item['codigo']}) {item['nome']}: {item['estoque_atual']} {item['unidade_medida']}\n"
            return response
        except Exception as e:
            logging.error(f"Erro ao visualizar estoque: {e}", exc_info=True)
            return "❌ Erro ao buscar itens do estoque."

    def _handle_estoque_add(self, args: list):
        """Adiciona um novo item ao estoque."""
        # !estoque add [codigo] "[Nome do Item]" [Grupo] [Qtd. Inicial] [Unidade]
        try:
            if len(args) < 5:
                return 'Uso: /estoque add <codigo> "<Nome>" <Grupo> <Qtd> <Unidade>'

            codigo = args[0]
            
            # Extrai o nome do item (pode estar entre aspas)
            nome_parts = []
            in_name = False
            i = 1
            for i, part in enumerate(args[1:], start=1):
                if part.startswith('"') and not in_name:
                    in_name = True
                    nome_parts.append(part[1:])
                elif in_name:
                    if part.endswith('"'):
                        nome_parts.append(part[:-1])
                        break
                    else:
                        nome_parts.append(part)
            nome = " ".join(nome_parts)
            
            remaining_args = args[i+1:]
            grupo_nome = remaining_args[0]
            qtd_inicial = int(remaining_args[1])
            unidade = " ".join(remaining_args[2:])

            # Valida se o grupo existe
            grupos = db.get_all_groups()
            grupo_id = next((g['id'] for g in grupos if g['nome'].lower() == grupo_nome.lower()), None)
            if not grupo_id:
                return f"❌ Grupo '{grupo_nome}' não encontrado."

            # Adiciona o item
            from stock_manager import add_item
            success, message = add_item({
                'codigo': codigo, 'nome': nome, 'grupo_id': grupo_id,
                'estoque_atual': qtd_inicial, 'estoque_minimo': 0, 'unidade_medida': unidade
            })

            if success:
                return f"✅ Item '{nome}' adicionado ao estoque com {qtd_inicial} {unidade}."
            else:
                return f"❌ {message}"
        except (ValueError, IndexError):
            return 'Uso inválido. Exemplo: /estoque add GR01 "Granola 500g" Insumos 10 pct'
        except Exception as e:
            logging.error(f"Erro ao adicionar item ao estoque: {e}", exc_info=True)
            return "❌ Erro interno ao adicionar item."

    def _handle_estoque_baixa(self, args: list):
        """Dá baixa em um ou mais itens do estoque."""
        if not args:
            return "Uso: /estoque baixa <codigo1> <qtd1>, <codigo2> <qtd2>, ..."
        
        try:
            items_str = " ".join(args)
            items_to_decrease = [item.strip().split() for item in items_str.split(',')]
            
            responses = []
            from stock_manager import decrease_stock
            for item_code, quantity_str in items_to_decrease:
                quantity = int(quantity_str)
                success, message = decrease_stock(item_code, quantity)
                if success:
                    responses.append(f"✅ Baixa de {quantity} em '{item_code}' realizada.")
                else:
                    responses.append(f"❌ Falha na baixa de '{item_code}': {message}")
            
            return "\n".join(responses)
        except (ValueError, IndexError):
            return "Formato inválido. Exemplo: /estoque baixa GR01 1, CP300 50"
        except Exception as e:
            logging.error(f"Erro ao dar baixa no estoque: {e}", exc_info=True)
            return "❌ Erro interno ao processar baixa de estoque."

    def _handle_estoque_ajustar(self, args: list):
        """Ajusta o estoque de um produto."""
        try:
            if len(args) != 2:
                return "Uso: /estoque ajustar <código_item> <nova_quantidade>"

            item_code = args[0]
            new_stock = int(args[1])

            from stock_manager import adjust_stock
            success, message = adjust_stock(item_code, new_stock)

            if success:
                return f"✅ Estoque do item '{item_code}' ajustado para {new_stock}."
            else:
                return f"❌ {message}"

        except ValueError:
            return "❌ Quantidade inválida. Por favor, insira um número inteiro."
        except Exception as e:
            logging.error(f"Erro ao ajustar estoque via comando: {e}", exc_info=True)
            return "❌ Ocorreu um erro interno ao ajustar o estoque."

    def _handle_estoque_baixo(self):
        """Retorna uma lista de produtos com estoque baixo."""
        try:
            report = db.get_stock_report()
            low_stock_items = report.get('low_stock_items', [])

            if not low_stock_items:
                return "✅ Nenhum produto com estoque baixo encontrado."

            response = "📉 *Produtos com Estoque Baixo*\n\n"
            for item in low_stock_items:
                stock_str = f"{item['stock']:.3f}".replace('.', ',')
                response += f"- `{item['description']}`: `{stock_str}`\n"
            
            return response

        except Exception as e:
            logging.error(f"Erro ao buscar produtos com estoque baixo via comando: {e}", exc_info=True)
            return "❌ Ocorreu um erro interno ao buscar o relatório de estoque."

    def _handle_caixa_movimento(self, tipo: str, args: list):
        """Registra uma sangria ou suprimento no caixa."""
        try:
            if len(args) < 2:
                return f"Uso: /caixa {tipo} <valor> <motivo>"

            valor_str = args[0].replace(',', '.')
            valor = float(valor_str)
            motivo = " ".join(args[1:])

            session = db.get_current_cash_session()
            if not session:
                return "❌ Operação falhou: Não há caixa aberto."

            # A ação é atribuída ao usuário 'admin' por padrão para operações via WhatsApp
            admin_user = db.get_user_by_username('admin')
            if not admin_user:
                return "❌ Operação falhou: Usuário 'admin' padrão não encontrado no sistema."

            session_id = session['id']
            user_id = admin_user['id']

            db.add_cash_movement(session_id, user_id, tipo, valor, motivo)
            
            tipo_str_upper = tipo.upper()
            return f"✅ *{tipo_str_upper}* de `R$ {valor:.2f}` registrada com sucesso no caixa."

        except ValueError:
            return "❌ Valor inválido. Por favor, insira um número (ex: 50.75)."
        except Exception as e:
            logging.error(f"Erro ao registrar {tipo} via comando: {e}", exc_info=True)
            return f"❌ Ocorreu um erro interno ao registrar a {tipo}."

    def _handle_caixa_status(self):
        """Retorna o status detalhado do caixa atual."""
        try:
            status = db.get_current_cash_status()
            if status.get('status') == 'FECHADO':
                return "ℹ️ O caixa está fechado no momento."

            open_time_str = status['open_time'].strftime('%d/%m/%Y às %H:%M')
            
            response = (
                f"📦 *Status do Caixa (Aberto)*\n\n"
                f"👤 *Operador:* `{status['username']}`\n"
                f"⏰ *Abertura:* `{open_time_str}`\n\n"
                f"💰 *Saldo Inicial:* `R$ {status['initial_amount']:.2f}`\n"
                f"➕ *Suprimentos:* `R$ {status['suprimentos']:.2f}`\n"
                f"➖ *Sangrias:* `R$ {status['sangrias']:.2f}`\n"
                f"📈 *Vendas (Dinheiro):* `R$ {status['cash_sales']:.2f}`\n\n"
                f"💵 *Saldo Atual em Dinheiro:* `R$ {status['current_balance']:.2f}`"
            )
            return response
        except Exception as e:
            logging.error(f"Erro ao obter status do caixa via comando: {e}", exc_info=True)
            return "❌ Ocorreu um erro interno ao buscar o status do caixa."

    def _handle_status(self, args, manager):
        """Verifica e retorna o status da integração WhatsApp."""
        try:
            health = manager.get_health_status()
            
            status_icon = "✅" if health['connected'] else "❌"
            worker_icon = "✅" if health['worker_running'] else "❌"
            
            duration_seconds = health['connection_duration']
            minutes, seconds = divmod(duration_seconds, 60)
            hours, minutes = divmod(minutes, 60)
            duration_str = f"{int(hours)}h {int(minutes)}m {int(seconds)}s"

            response = (
                f"🩺 *Status da Integração WhatsApp*\n\n"
                f"{status_icon} *Conectado:* `{str(health['connected'])}`\n"
                f"{worker_icon} *Serviço Ativo:* `{str(health['worker_running'])}`\n"
                f"⏱️ *Tempo de Conexão:* `{duration_str}`\n"
                f" caching *Cache de Números:* `{health['cache_size']}`\n"
                f"📜 *Histórico de Msgs:* `{health['message_history_count']}`"
            )
            return response
        except Exception as e:
            logging.error(f"Erro ao obter status da integração: {e}", exc_info=True)
            return "❌ Não foi possível obter o status da integração."

    def _handle_logs(self, args, manager):
        """Lê e retorna as últimas linhas do log do sistema."""
        try:
            # O nível de log é o primeiro argumento, o número de linhas é o segundo.
            log_level_filter = args[0].upper() if args else None
            num_lines = int(args[1]) if len(args) > 1 else 5

            log_file_path = manager.logger.log_file

            if not os.path.exists(log_file_path):
                return "❌ Arquivo de log não encontrado."

            relevant_lines: List[Dict[str, Any]] = []
            with open(log_file_path, 'r', encoding='utf-8') as f:
                all_lines = f.readlines()

            # Itera sobre as linhas de trás para frente para pegar as mais recentes
            for line in reversed(all_lines):
                if len(relevant_lines) >= num_lines:
                    break
                try:
                    log_entry = json.loads(line.strip())
                    # Se um filtro de nível foi fornecido, aplica-o
                    if log_level_filter:
                        if log_entry.get('level') == log_level_filter:
                            relevant_lines.append(log_entry)
                    else:
                        # Se não houver filtro, adiciona qualquer linha válida
                        relevant_lines.append(log_entry)
                except (json.JSONDecodeError, AttributeError):
                    continue  # Ignora linhas que não são JSON válido

            if not relevant_lines:
                return f"ℹ️ Nenhum log encontrado para o nível '{log_level_filter}'." if log_level_filter else "ℹ️ O arquivo de log está vazio."

            # Inverte a lista para que os logs fiquem em ordem cronológica
            relevant_lines.reverse()

            response = f"📜 *Últimos {len(relevant_lines)} Logs ({log_level_filter or 'Todos'})*\n\n"
            for entry in relevant_lines:
                timestamp = datetime.fromisoformat(entry['timestamp']).strftime('%H:%M:%S')
                level = entry.get('level', 'N/A')
                message = entry.get('message', 'Mensagem não encontrada')
                
                icon = "🔴" if level == "ERROR" else "🟡" if level == "WARNING" else "🔵" if level == "CONNECTION" else "⚪"
                
                # Limita o tamanho da mensagem para não poluir o chat
                message_preview = message if len(message) < 100 else message[:100] + '...'
                response += f"`{timestamp}` {icon} *{level}* - {message_preview}\n"
            
            return response.strip()

        except ValueError:
            return "❌ Uso inválido. O número de linhas deve ser um número. Ex: `/logs ERROR 10`"
        except Exception as e:
            logging.error(f"Erro ao manusear comando /logs: {e}", exc_info=True)
            return "❌ Ocorreu um erro interno ao processar os logs."
