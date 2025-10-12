# Conteúdo para integrations/whatsapp_command_handler.py
import logging
from datetime import datetime, timedelta
import database as db
import stock_manager as sm
import re
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

    def process_command(self, command_data: dict, manager):
        """
        Processa um comando, registra a auditoria e retorna a resposta e o destinatário.
        Recebe a instância do manager para acessar métodos de status e logging.
        Retorna: Uma lista de tuplas (response_text, recipient_phone) ou None.
        """
        sender_phone_raw = command_data.get('sender')
        command_text = command_data.get('text', '').strip()

        # Normaliza o número do remetente antes de verificar
        validation = self.config.validate_phone(sender_phone_raw)
        if not validation['valid']:
            logging.warning(f"Número de remetente com formato inválido foi ignorado: {sender_phone_raw}")
            return None
        
        sender_phone = validation['normalized']

        # A verificação agora usa a lista normalizada em cache.
        if not sender_phone or sender_phone not in self.authorized_managers:
            logging.warning(f"Comando de número não autorizado foi ignorado: {sender_phone} (Lista de autorizados: {self.authorized_managers})")
            # Log de tentativa de comando não autorizado
            manager.logger.log_command(sender=sender_phone, command=command_text, success=False, response_preview="Acesso negado")
            return None

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
            '/fiados': self._handle_fiados,
            '/pagar': self._handle_pagar,
            '/lembrete': self._handle_lembrete,
        }

        handler_func = command_map.get(command)
        if handler_func:
            # Passa o manager para handlers que precisam dele
            if command in ['/status', '/logs', '/gerente', '/sistema', '/lembrete']:
                response = handler_func(args, manager=manager)
            else:
                response = handler_func(args)
            
            # Garante que a resposta seja sempre uma lista de tuplas (mensagem, destinatário)
            if not isinstance(response, list):
                response = [(response, sender_phone)]
            
            final_responses = []
            for msg, recipient in response:
                # Se o destinatário for None, assume que a resposta é para o remetente original
                final_recipient = recipient if recipient is not None else sender_phone
                final_responses.append((msg, final_recipient))

            # Log de comando bem-sucedido
            manager.logger.log_command(sender=sender_phone, command=command_text, success=True, response_preview=str(final_responses))
            return final_responses
        else:
            response = f"Comando '{command}' não reconhecido. Digite '/ajuda' para ver a lista de comandos."
            # Log de comando não reconhecido
            manager.logger.log_command(sender=sender_phone, command=command_text, success=False, response_preview="Comando não reconhecido")
            return [(response, sender_phone)]

    def _handle_help(self, args):
        """Retorna a mensagem de ajuda com os comandos disponíveis."""
        return (
            "🤖 *Assistente Virtual PDV* 🤖\n\n"
            "Aqui estão os comandos que você pode usar:\n\n"
            "📈 *DASHBOARD*\n"
            "  `*/dashboard`* - Resumo completo do dia.\n\n"
            "📊 *RELATÓRIOS*\n"
            "  `*/vendas <período>`* - Vendas do período (hoje, ontem, 7dias, etc.).\n"
            "  `*/produtos_vendidos <período>`* - Ranking de produtos mais vendidos.\n\n"
            "💳 *CONTROLE DE FIADO*\n"
            "  `*/fiados [cliente]`* - Lista os fiados pendentes (filtra por cliente se informado).\n"
            "  `*/pagar <id_fiado> <valor> <método>`* - Registra um pagamento para um fiado.\n"
            "  `*/lembrete <id_fiado>`* - Envia um lembrete de cobrança para o cliente.\n"
            "  `*/fiado criar \"<nome cliente>\" <valor> [obs]`* - Cria um novo fiado.\n"
            "  `*/fiado editar <id> <campo> <novo_valor>`* - Edita um fiado (campos: valor, vencimento, obs).\n"
            "  `*/fiado cancelar <id>`* - Cancela um fiado.\n\n"
            "📦 *CAIXA*\n"
            "  `*/caixa status`* - Status detalhado do caixa atual.\n"
            "  `*/caixa fechar`* - Relatório de pré-fechamento.\n"
            "  `*/caixa sangria <valor> <motivo>`* - Registrar sangria.\n"
            "  `*/caixa suprimento <valor> <motivo>`* - Registrar suprimento.\n\n"
            "📝 *PRODUTOS (VENDA)*\n"
            "  `*/produto consultar <nome/cód>`* - Detalhes de um produto de venda.\n"
            "  `*/produto alterar_preco <cód> <preço>`* - Altera o preço de um produto de venda.\n\n"
            "📋 *ESTOQUE (INSUMOS)*\n"
            "  `*/estoque grupos`* - Lista os grupos de insumos.\n"
            "  `*/estoque ver`* - Lista todos os insumos por grupo.\n"
            "  `*/estoque add <grupo> <unid> | <cód> \"<nome>\" <qtd>[; ...]`* - Adiciona múltiplos insumos a um grupo.\n"
            "  `*/estoque baixa <cód1> <qtd1>, <cód2> <qtd2>`* - Dá baixa em um ou mais insumos.\n"
            "  `*/estoque ajustar <cód> <nova_qtd>`* - Ajusta a quantidade de um insumo.\n\n"
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

    def _handle_fiados(self, args: list):
        """Lida com subcomandos relacionados a fiados."""
        if not args:
            # Mantém o comportamento original de listar se nenhum subcomando for dado
            return self._handle_fiados_listar([])

        subcommand = args[0].lower()
        command_args = args[1:]

        if subcommand == 'listar':
            return self._handle_fiados_listar(command_args)
        elif subcommand == 'criar':
            return self._handle_fiados_criar(command_args)
        elif subcommand == 'editar':
            return self._handle_fiados_editar(command_args)
        elif subcommand == 'cancelar':
            return self._handle_fiados_cancelar(command_args)
        else:
            # Se o primeiro argumento não for um subcomando conhecido, assume que é uma busca
            return self._handle_fiados_listar(args)

    def _handle_fiados_listar(self, args: list):
        """Lista os fiados pendentes, com filtro opcional por cliente."""
        try:
            if not args:
                # Lista todos os fiados pendentes e parcialmente pagos
                sales = db.get_credit_sales(status_filter='pending')
                sales += db.get_credit_sales(status_filter='partially_paid')
            else:
                # Filtra por nome do cliente
                customer_name = " ".join(args)
                all_sales = db.get_credit_sales(status_filter='pending')
                all_sales += db.get_credit_sales(status_filter='partially_paid')
                sales = [s for s in all_sales if customer_name.lower() in s['customer_name'].lower()]

            if not sales:
                return "✅ Nenhum fiado pendente encontrado." if not args else f"✅ Nenhum fiado pendente encontrado para o cliente '{customer_name}'."

            response = "🧾 *Fiados Pendentes*\n\n"
            for sale in sorted(sales, key=lambda x: x['customer_name']):
                response += f"*ID:* `{sale['id']}` - *Cliente:* {sale['customer_name']}\n"
                response += f"  - *Saldo Devedor:* `R$ {sale['balance_due']:.2f}`\n"
                response += f"  - *Data:* {sale['created_date'][:10]}\n"
            
            return response.strip()
        except Exception as e:
            logging.error(f"Erro ao listar fiados via comando: {e}", exc_info=True)
            return "❌ Ocorreu um erro interno ao buscar os fiados."

    def _handle_fiados_criar(self, args: list):
        """Cria um novo fiado. Uso: /fiado criar \"<nome cliente>\" <valor> [obs]"""
        try:
            # Regex para capturar o nome entre aspas e o resto
            match = re.match(r'^"([^"]+)"\s+([\d,.]+)(.*)$', " ".join(args))
            if not match:
                return 'Uso: /fiado criar "<nome do cliente>" <valor> [observações]'

            customer_name, value_str, observations = match.groups()
            value = float(value_str.replace(',', '.'))
            observations = observations.strip() or None

            # Busca pelo cliente
            customers = db.search_customers(customer_name)
            if not customers:
                return f'❌ Cliente "{customer_name}" não encontrado. Cadastre o cliente primeiro.'
            if len(customers) > 1:
                return f'❌ Múltiplos clientes encontrados para "{customer_name}". Por favor, seja mais específico.'
            
            customer = customers[0]
            admin_user = db.get_user_by_username('admin')

            success, result = db.create_credit_sale(
                customer_id=customer['id'],
                amount=value,
                user_id=admin_user['id'],
                observations=observations
            )

            if success:
                return f"✅ Novo fiado de `R$ {value:.2f}` criado com sucesso para o cliente *{customer['name']}* (ID do Fiado: {result})."
            else:
                return f"❌ Falha ao criar fiado: {result}"

        except Exception as e:
            logging.error(f"Erro ao criar fiado via comando: {e}", exc_info=True)
            return "❌ Ocorreu um erro interno ao criar o fiado."

    def _handle_fiados_editar(self, args: list):
        """Edita um fiado. Uso: /fiado editar <id> <campo> <novo_valor>"""
        return "ℹ️ A função de editar fiado via WhatsApp ainda não foi implementada."

    def _handle_fiados_cancelar(self, args: list):
        """Cancela um fiado. Uso: /fiado cancelar <id>"""
        try:
            if len(args) != 1:
                return "Uso: /fiado cancelar <id_do_fiado>"
            
            credit_sale_id = int(args[0])
            admin_user = db.get_user_by_username('admin')

            success, message = db.update_credit_sale_status(credit_sale_id, 'cancelled', admin_user['id'])

            if success:
                return f"✅ Fiado ID `{credit_sale_id}` foi cancelado com sucesso."
            else:
                return f"❌ Falha ao cancelar fiado: {message}"
        except ValueError:
            return "❌ ID do fiado inválido."
        except Exception as e:
            logging.error(f"Erro ao cancelar fiado via comando: {e}", exc_info=True)
            return "❌ Ocorreu um erro interno ao cancelar o fiado."

    def _handle_pagar(self, args: list):
        """Registra um pagamento para um fiado. Uso: /pagar <id_fiado> <valor> <método>"""
        try:
            if len(args) < 3:
                return "Uso: /pagar <id_fiado> <valor> <método> (Ex: /pagar 123 50.00 Dinheiro)"

            credit_sale_id = int(args[0])
            amount_paid_str = args[1].replace(',', '.')
            amount_paid = float(amount_paid_str)
            payment_method = " ".join(args[2:])

            # Valida o método de pagamento
            valid_methods = [m['name'] for m in db.get_all_payment_methods()]
            if payment_method not in valid_methods:
                return f"❌ Método de pagamento '{payment_method}' inválido. Métodos válidos: {', '.join(valid_methods)}"

            sale_details = db.get_credit_sale_details(credit_sale_id)
            if not sale_details:
                return f"❌ Fiado com ID '{credit_sale_id}' não encontrado."

            if sale_details['status'] in ['paid', 'cancelled']:
                return f"ℹ️ O fiado com ID '{credit_sale_id}' já está quitado ou cancelado."

            balance_due = sale_details['balance_due']
            if amount_paid > float(balance_due):
                return f"❌ Valor do pagamento (R$ {amount_paid:.2f}) é maior que o saldo devedor (R$ {balance_due:.2f})."

            admin_user = db.get_user_by_username('admin')
            if not admin_user:
                return "❌ Operação falhou: Usuário 'admin' padrão não encontrado no sistema."

            success, message = db.add_credit_payment(credit_sale_id, amount_paid, admin_user['id'], payment_method)

            if success:
                new_sale_details = db.get_credit_sale_details(credit_sale_id)
                response = f"✅ Pagamento de `R$ {amount_paid:.2f}` registrado para o fiado ID `{credit_sale_id}`.\n\n"
                response += f"*Cliente:* {new_sale_details['customer_name']}\n"
                if new_sale_details['status'] == 'paid':
                    response += "*Status:* `QUITADO` 🎉"
                else:
                    response += f"*Novo Saldo Devedor:* `R$ {new_sale_details['balance_due']:.2f}`"
                return response
            else:
                return f"❌ Falha ao registrar pagamento: {message}"

        except ValueError:
            return "❌ ID do fiado ou valor do pagamento inválido."
        except Exception as e:
            logging.error(f"Erro ao registrar pagamento de fiado via comando: {e}", exc_info=True)
            return "❌ Ocorreu um erro interno ao registrar o pagamento."

    def _handle_lembrete(self, args: list, manager):
        """Envia um lembrete de cobrança para o cliente de um fiado. Uso: /lembrete <id_fiado>"""
        try:
            if len(args) != 1:
                return "Uso: /lembrete <id_fiado>"

            credit_sale_id = int(args[0])
            sale_details = db.get_credit_sale_details(credit_sale_id)

            if not sale_details:
                return f"❌ Fiado com ID '{credit_sale_id}' não encontrado."

            if sale_details['status'] not in ['pending', 'partially_paid']:
                return f"ℹ️ Este fiado já está quitado ou foi cancelado."

            customer_id = sale_details['customer_id']
            customer_details = db.get_customer_by_id(customer_id)
            if not customer_details:
                return f"❌ Cliente com ID '{customer_id}' não encontrado no sistema."

            customer_phone = customer_details.get('phone')

            if not customer_phone:
                return f"❌ O cliente {sale_details['customer_name']} não possui um número de telefone cadastrado."

            # Valida e normaliza o número do cliente
            validation = self.config.validate_phone(customer_phone)
            if not validation['valid']:
                return f"❌ O número de telefone do cliente ({customer_phone}) é inválido."
            
            normalized_customer_phone = validation['normalized']

            # Mensagem para o cliente
            store_name = db.load_setting('store_name', 'nossa loja')
            reminder_message = (
                f"Olá, {sale_details['customer_name']}! 👋\n\n"
                f"Este é um lembrete amigável sobre sua conta pendente em {store_name}.\n\n"
                f"*Saldo Devedor:* R$ {sale_details['balance_due']:.2f}\n"
                f"*Data da Compra:* {sale_details['created_date'][:10]}\n\n"
                f"Agradecemos a sua atenção e preferência!"
            )

            # Mensagem de confirmação para o gerente
            confirmation_message = f"✅ Lembrete enviado com sucesso para o cliente {sale_details['customer_name']} (Telefone: {normalized_customer_phone})."

            # Retorna uma lista de tuplas (mensagem, destinatário)
            return [
                (reminder_message, normalized_customer_phone),
                (confirmation_message, None) # O destinatário None será substituído pelo remetente original
            ]

        except ValueError:
            return "❌ ID do fiado inválido."
        except Exception as e:
            logging.error(f"Erro ao enviar lembrete de fiado via comando: {e}", exc_info=True)
            return "❌ Ocorreu um erro interno ao enviar o lembrete."

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
        """Lida com subcomandos para o novo sistema de estoque de insumos."""
        if not args:
            return "Uso: /estoque [ver|grupos|add|baixa|ajustar] <argumentos...>"

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
        else:
            return f"Subcomando '/estoque {subcommand}' não reconhecido. Use '/ajuda' para ver as opções."

    def _handle_estoque_grupos(self):
        """Lista os grupos de estoque de insumos."""
        try:
            groups = sm.get_all_stock_groups()
            if not groups:
                return "ℹ️ Nenhum grupo de estoque encontrado."
            
            response = "📂 *Grupos de Estoque (Insumos)*\n\n"
            for group in groups:
                response += f"- {group['nome']}\n"
            return response
        except Exception as e:
            logging.error(f"Erro ao listar grupos de estoque via comando: {e}", exc_info=True)
            return "❌ Ocorreu um erro interno ao buscar os grupos."

    def _handle_estoque_ver(self):
        """Lista todos os itens de estoque, organizados por grupo."""
        try:
            items = sm.get_all_stock_items()
            if not items:
                return "ℹ️ Nenhum item de estoque encontrado."

            response = "📋 *Estoque de Insumos*\n"
            current_group = None
            for item in items:
                if item['grupo_nome'] != current_group:
                    current_group = item['grupo_nome']
                    response += f"\n--- *{current_group}* ---\n"
                response += f"({item['codigo']}) {item['nome']}: *{item['estoque_atual']}* {item['unidade_medida']}\n"
            return response.strip()
        except Exception as e:
            logging.error(f"Erro ao visualizar estoque via comando: {e}", exc_info=True)
            return "❌ Ocorreu um erro interno ao buscar o estoque."

    def _handle_estoque_add(self, args: list):
        """Adiciona múltiplos itens de estoque a um grupo. Formato: <grupo> <unid> | <cód> \"<nome>\" <qtd>; ..."""
        try:
            full_command = " ".join(args)
            if '|' not in full_command:
                return '❌ Formato inválido. Use: /estoque add <grupo> <unid> | <cód> "<nome>" <qtd>[; ...]'

            header_part, items_part = [part.strip() for part in full_command.split('|', 1)]

            # Processar o cabeçalho
            header_args = header_part.split()
            if len(header_args) != 2:
                return "❌ Formato do cabeçalho inválido. Deve ser `<grupo> <unidade>`."
            grupo_nome, unidade_medida = header_args

            # Validar grupo
            all_groups = sm.get_all_stock_groups()
            target_group = next((g for g in all_groups if g['nome'].lower() == grupo_nome.lower()), None)
            if not target_group:
                return f"❌ Grupo '{grupo_nome}' não encontrado."
            grupo_id = target_group['id']

            # Processar os itens
            items_to_add = [item.strip() for item in items_part.split(';') if item.strip()]
            if not items_to_add:
                return "❌ Nenhum item fornecido após o separador '|'."

            success_log = []
            error_log = []
            item_regex = re.compile(r'^(\S+)\s+"([^"]+)"\s+(\d+)$')

            for item_str in items_to_add:
                match = item_regex.match(item_str)
                if not match:
                    error_log.append(f"'{item_str}' (formato inválido)")
                    continue
                
                codigo, nome, qtd_str = match.groups()
                
                success, message = sm.add_stock_item(
                    codigo=codigo.upper(),
                    nome=nome,
                    grupo_id=grupo_id,
                    estoque_atual=int(qtd_str),
                    estoque_minimo=0, # Padrão
                    unidade_medida=unidade_medida
                )
                if success:
                    success_log.append(f"'{nome}' ({codigo.upper()})")
                else:
                    error_log.append(f"'{nome}' ({message})" )

            # Montar resposta final
            response = "" 
            if success_log:
                response += f"✅ *Itens Adicionados ao Grupo '{grupo_nome}':*\n" + ", ".join(success_log) + ".\n"
            if error_log:
                response += f"\n❌ *Falhas ao Adicionar:*\n" + ", ".join(error_log) + "."
            
            return response.strip() if response else "Nenhuma ação realizada."

        except Exception as e:
            logging.error(f"Erro ao adicionar múltiplos itens de estoque via comando: {e}", exc_info=True)
            return "❌ Ocorreu um erro interno ao processar o comando."

    def _handle_estoque_baixa(self, args: list):
        """Dá baixa em um ou mais itens do estoque. Formato: <cód1> <qtd1>, <cód2> <qtd2>"""
        try:
            full_command = " ".join(args)
            items_to_process = [item.strip() for item in full_command.split(',') if item.strip()]

            if not items_to_process:
                return "❌ Formato inválido. Uso: /estoque baixa <cód1> <qtd1>, <cód2> <qtd2>"

            responses = []
            for item_str in items_to_process:
                parts = item_str.split()
                if len(parts) != 2:
                    responses.append(f"Ignorado: '{item_str}' (formato inválido)")
                    continue
                
                codigo, qtd_str = parts
                try:
                    qtd = int(qtd_str)
                    success, message = sm.give_stock_out(codigo.upper(), qtd)
                    if success:
                        item_info = sm.get_item_by_code(codigo.upper())
                        item_name = item_info['nome'] if item_info else codigo.upper()
                        responses.append(f"✅ Baixa de {qtd} em '{item_name}' realizada.")
                    else:
                        responses.append(f"❌ Falha ao dar baixa em '{codigo.upper()}': {message}")
                except ValueError:
                    responses.append(f"Ignorado: Quantidade para '{codigo.upper()}' não é um número.")
                except Exception as e:
                    responses.append(f"❌ Erro ao processar '{codigo.upper()}': {e}")
            
            return "\n".join(responses)

        except Exception as e:
            logging.error(f"Erro ao dar baixa no estoque via comando: {e}", exc_info=True)
            return "❌ Ocorreu um erro interno ao processar a baixa de estoque."

    def _handle_estoque_ajustar(self, args: list):
        """Ajusta a quantidade de um item de estoque para um novo valor."""
        try:
            if len(args) != 2:
                return "Uso: /estoque ajustar <código_item> <nova_quantidade>"

            codigo = args[0].upper()
            nova_qtd = int(args[1])

            item = sm.get_item_by_code(codigo)
            if not item:
                return f"❌ Item com código '{codigo}' não encontrado."

            success, message = sm.adjust_stock_quantity(codigo, nova_qtd)

            if success:
                return f"✅ Estoque de '{item['nome']}' ajustado para *{nova_qtd} {item['unidade_medida']}*."
            else:
                return f"❌ Falha ao ajustar estoque: {message}"

        except ValueError:
            return "❌ Quantidade inválida. Por favor, insira um número inteiro."
        except Exception as e:
            logging.error(f"Erro ao ajustar estoque via comando: {e}", exc_info=True)
            return "❌ Ocorreu um erro interno ao ajustar o estoque."

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
