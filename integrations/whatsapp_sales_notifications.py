"""
Sistema de notificações automáticas de vendas via WhatsApp.
Integra com o sistema de vendas para enviar notificações quando vendas são realizadas.
"""
import json
import os
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from decimal import Decimal
import logging

from .whatsapp_manager import WhatsAppManager
from .whatsapp_config import get_whatsapp_config
from utils import get_data_path
import database as db
from data.payment_method_repository import get_all_payment_methods

class WhatsAppSalesNotifier:
    """
    Notificador de vendas que envia mensagens automáticas via WhatsApp.
    """

    def __init__(self):
        self.manager = WhatsAppManager.get_instance()
        self.config = get_whatsapp_config()
        self._notification_settings_path = get_data_path('whatsapp_sales_notifications.json')
        self._load_notification_settings()
        self._recent_sale_ids = {}

    def _load_notification_settings(self):
        """Carrega configurações de notificações."""
        try:
            if os.path.exists(self._notification_settings_path):
                with open(self._notification_settings_path, 'r', encoding='utf-8') as f:
                    self.notification_settings = json.load(f)
            else:
                self.notification_settings = self._get_default_settings()
                self._save_notification_settings()
        except Exception as e:
            logging.error(f"Erro ao carregar configurações de notificações: {e}", exc_info=True)
            self.notification_settings = self._get_default_settings()

    def _save_notification_settings(self):
        """Salva configurações de notificações."""
        try:
            with open(self._notification_settings_path, 'w', encoding='utf-8') as f:
                json.dump(self.notification_settings, f, indent=4, ensure_ascii=False)
        except Exception as e:
            logging.error(f"Erro ao salvar configurações de notificações: {e}", exc_info=True)

    def _get_default_settings(self) -> Dict[str, Any]:
        """Retorna configurações padrão."""
        return {
            'enable_sale_notifications': True,
            'enable_cash_notifications': True,
            'enable_low_stock_alerts': False,
            'notification_recipients': [],
            'detailed_payment_breakdown': True,
            'minimum_sale_value': 0.0,
            'notification_delay': 0,  # segundos
            'custom_message_templates': {},
            'last_notification_times': {}
        }

    def notify_sale(self, sale_data: Dict[str, Any], payment_details: List[Dict[str, Any]], change_amount: float) -> bool:
        """
        Notifica uma venda realizada.

        Args:
            sale_data: Dados da venda (id, customer_name, total_amount, etc.)
            payment_details: Lista de pagamentos com método e valor
            change_amount: Valor do troco

        Returns:
            bool: True se notificou com sucesso
        """
        try:
            # Anti-duplication check
            sale_id = sale_data.get('id')
            now = datetime.now()

            # Clean up old entries from the cache (older than 1 minute)
            cleanup_time = now - timedelta(minutes=1)
            keys_to_delete = [k for k, v in self._recent_sale_ids.items() if v < cleanup_time]
            for k in keys_to_delete:
                del self._recent_sale_ids[k]

            # Block if notified within the last 15 seconds
            if sale_id in self._recent_sale_ids:
                time_since_notification = now - self._recent_sale_ids[sale_id]
                if time_since_notification < timedelta(seconds=15):
                    logging.warning(f"Tentativa de notificação duplicada bloqueada para a venda ID: {sale_id}")
                    return True  # Return True to signal success and prevent re-queueing

            if not db.are_notifications_globally_enabled():
                logging.info("Envio de notificação de venda ignorado (desativado globalmente).")
                return True

            # Verificar se notificações estão habilitadas
            if not self.notification_settings.get('enable_sale_notifications', False):
                return True

            # Verificar valor mínimo
            min_value = self.notification_settings.get('minimum_sale_value', 0.0)
            if float(sale_data.get('total_amount', 0)) < min_value:
                return True
            
            # Add sale ID to cache before sending
            if sale_id:
                self._recent_sale_ids[sale_id] = now

            # Construir mensagem detalhada
            message = self._build_sale_message(sale_data, payment_details, change_amount)

            if not message:
                return False

            # Enviar para todos os destinatários configurados
            recipients = self._get_notification_recipients()
            success_count = 0

            for phone in recipients:
                try:
                    result = self.manager.send_message(phone, message, message_type='system_automatic')
                    if result.get('success'):
                        success_count += 1
                    else:
                        logging.warning(f"Falha ao enviar notificação para {phone}: {result.get('error')}")
                except Exception as e:
                    logging.error(f"Erro ao enviar notificação para {phone}: {e}", exc_info=True)

            return success_count > 0

        except Exception as e:
            logging.error(f"Erro ao notificar venda: {e}", exc_info=True)
            return False

    def notify_cash_opening(self, user_name: str, initial_amount: float, summary_dict: Dict[str, Any]) -> bool:
        """Notifica abertura de caixa."""
        try:
            if not db.are_notifications_globally_enabled():
                logging.info("Envio de notificação de abertura de caixa ignorado (desativado globalmente).")
                return True

            if not self.notification_settings.get('enable_cash_notifications', False):
                return True

            # Correção do Bug de Horário: Captura a hora exata do envio
            now_str = datetime.now().strftime('%d/%m/%Y %H:%M')

            message = (
                f"✅ *CAIXA ABERTO* ✅\n\n"
                f"*{self._get_store_name()}*\n\n"
                f"🗓️ *Data/Hora:* {now_str}\n"
                f"👤 *Operador:* {user_name}\n"
                f"💰 *Saldo Inicial:* R$ {initial_amount:.2f}\n"
                f"🆔 *Sessão:* #{summary_dict.get('id', 'N/A')}\n\n"
                f"_Uma nova sessão de caixa foi iniciada._"
            )

            recipients = self._get_notification_recipients()
            success_count = 0
            for phone in recipients:
                result = self.manager.send_message(phone, message, message_type='system_automatic')
                if result.get('success'):
                    success_count += 1
            return success_count > 0
        except Exception as e:
            logging.error(f"Erro ao notificar abertura de caixa: {e}", exc_info=True)
            return False

    def notify_cash_closing(self, report: Dict[str, Any]) -> bool:
        """Notifica fechamento de caixa com um relatório detalhado."""
        try:
            if not db.are_notifications_globally_enabled():
                logging.info("Envio de notificação de fechamento de caixa ignorado (desativado globalmente).")
                return True

            if not self.notification_settings.get('enable_cash_notifications', False):
                return True

            session = report.get('session', {})
            sales = report.get('sales', [])
            movements = report.get('movements', [])
            total_weight_kg = report.get('total_weight_kg', 0.0)
            credit_sales_created = report.get('credit_sales_created', [])
            credit_payments_received = report.get('credit_payments_received', [])

            # --- Formatação da Mensagem ---
            user_name = session.get('username', 'N/A')
            open_time = session.get('open_time').strftime('%d/%m/%Y %H:%M') if session.get('open_time') else 'N/A'
            close_time = session.get('close_time').strftime('%H:%M') if session.get('close_time') else 'N/A'

            initial = Decimal(session.get('initial_amount', 0))
            expected = Decimal(session.get('expected_amount', 0))
            final = Decimal(session.get('final_amount', 0))
            difference = Decimal(session.get('difference', 0))

            # Resumo de Vendas por método de pagamento
            sales_summary = "*VENDAS REALIZADAS:*\n"
            if not sales:
                sales_summary += "_Nenhuma venda registrada._\n"
            else:
                for sale in sales:
                    sales_summary += f"  • {sale['payment_method']}: R$ {sale['total']:.2f} ({sale['count']} vendas)\n"

            # Total de vendas (sem movimentações)
            total_sales_revenue = sum(Decimal(s['total']) for s in sales)
            sales_summary += f"\n💰 *TOTAL DAS VENDAS:* R$ {total_sales_revenue:.2f}\n"

            if total_weight_kg > 0:
                sales_summary += f"⚖️ *Açaí Vendido:* {total_weight_kg:.3f} kg\n"

            # Movimentações de Caixa Detalhadas
            movements_summary = "\n💸 *MOVIMENTAÇÕES DE CAIXA:*\n"
            if not movements:
                movements_summary += "_Nenhuma movimentação registrada._\n"
            else:
                for move in movements:
                    symbol = '➕' if move['type'] == 'suprimento' else '➖'
                    movements_summary += f"  {symbol} {move['type'].capitalize()}: R$ {move['amount']:.2f} ({move['reason']})\n"

            # Total Geral (vendas + movimentações)
            supplies_total = sum(Decimal(m['amount']) for m in movements if m['type'] == 'suprimento')
            withdrawals_total = sum(Decimal(m['amount']) for m in movements if m['type'] == 'sangria')
            total_geral = total_sales_revenue + supplies_total - withdrawals_total

            movements_summary += f"\n💵 *TOTAL GERAL (Vendas ± Movimentações):* R$ {total_geral:.2f}\n"

            # Resumo de Fiado (Crédito)
            credit_summary = "\n📝 *FIADO (CRÉDITO):*\n"
            if not credit_sales_created and not credit_payments_received:
                credit_summary += "_Nenhuma operação de fiado na sessão._\n"
            else:
                if credit_sales_created:
                    credit_summary += "*Novos Fiados:*\n"
                    for credit in credit_sales_created:
                        credit_summary += f"  • {credit['customer_name']}: R$ {credit['amount']:.2f}\n"
                if credit_payments_received:
                    credit_summary += "*Pagamentos Recebidos:*\n"
                    for payment in credit_payments_received:
                        credit_summary += f"  • {payment['customer_name']}: R$ {payment['total_paid']:.2f} ({payment['payment_method']})\n"

            # Fechamento e Diferença
            diff_symbol = "⚠️" if difference != 0 else "✅"
            diff_text = f"Sobra: +R$ {difference:.2f}" if difference > 0 else f"Falta: -R$ {abs(difference):.2f}" if difference < 0 else "Sem diferença"

            # Observações
            observations = report.get('observations', '')
            obs_summary = f"\n📝 *OBSERVAÇÕES:*\n_{observations}_\n" if observations else ""

            message = (
                f"❌ *FECHAMENTO DE CAIXA* ❌\n\n"
                f"🏪 *{self._get_store_name()}*\n\n"
                f"📅 *Data:* {open_time.split(' ')[0]}\n"
                f"👤 *Operador:* {user_name}\n"
                f"🕐 *Horário:* {open_time.split(' ')[1]} às {close_time}\n"
                f"🆔 *Sessão:* #{session.get('id', 'N/A')}\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"{sales_summary}\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"{movements_summary}\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"{credit_summary}\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"💵 *RESUMO FINAL:*\n"
                f"  • Saldo Inicial: R$ {initial:.2f}\n"
                f"  • Valor Esperado: R$ {expected:.2f}\n"
                f"  • Valor Contado: R$ {final:.2f}\n"
                f"  {diff_symbol} *Diferença:* {diff_text}\n"
                f"{obs_summary}"
            )

            recipients = self._get_notification_recipients()
            success_count = 0
            for phone in recipients:
                result = self.manager.send_message(phone, message, message_type='system_automatic')
                if result.get('success'):
                    success_count += 1
            return success_count > 0
        except Exception as e:
            logging.error(f"Erro ao notificar fechamento de caixa: {e}", exc_info=True)
            return False

    def notify_low_stock(self, product_data: Dict[str, Any]) -> bool:
        """Notifica produto com estoque baixo."""
        try:
            if not self.notification_settings.get('enable_low_stock_alerts', False):
                return True

            template = self.config.get_template('low_stock_alert')
            message = template.format(
                product_name=product_data.get('description', 'Produto'),
                current_stock=product_data.get('stock_quantity', 0),
                min_stock=product_data.get('min_stock', 0)
            )

            recipients = self._get_notification_recipients()
            success_count = 0

            for phone in recipients:
                result = self.manager.send_message(phone, message, message_type='system_automatic')
                if result.get('success'):
                    success_count += 1

            return success_count > 0

        except Exception as e:
            logging.error(f"Erro ao notificar estoque baixo: {e}", exc_info=True)
            return False

    def _build_sale_message(self, sale_data: Dict[str, Any], payment_details: List[Dict[str, Any]], change_amount: float) -> Optional[str]:
        """Constrói a mensagem de notificação de venda detalhada."""
        try:
            # --- Coleta de Dados ---
            now_str = datetime.now().strftime('%d/%m/%Y %H:%M')
            session_sale_id = sale_data.get("session_sale_id")

            # Correção para nome do cliente
            customer_name = sale_data.get("customer_name")
            if not customer_name or not customer_name.strip():
                customer_name = "Consumidor Final"
            else:
                customer_name = customer_name.strip()
            total_amount = Decimal(sale_data.get("total_amount", 0.0))
            discount_value = Decimal(sale_data.get("discount_value", 0.0))
            items = sale_data.get("items", [])
            change_amount = Decimal(change_amount)

            display_sale_id = session_sale_id if session_sale_id is not None else sale_data.get("id", "N/A")

            # --- Construção dos Itens ---
            items_str = ""
            for item in items:
                desc = item.get('description', 'N/A')
                total_price = Decimal(item.get('total_price', 0))
                if item.get('sale_type') == 'weight':
                    qty = Decimal(item.get('quantity', 0))
                    items_str += f"  - {desc} ({qty:.3f} kg) - R$ {total_price:.2f}\n"
                else:
                    qty = int(item.get('quantity', 0))
                    items_str += f"  - {desc} ({qty} un) - R$ {total_price:.2f}\n"

            # --- Construção do Pagamento (com detalhamento) ---
            payment_methods_from_db = db.get_all_payment_methods()
            payment_method_map = {method['id']: method['name'] for method in payment_methods_from_db}

            total_paid = sum(Decimal(p['amount']) for p in payment_details)
            payment_str = f"💰 *PAGAMENTO*\n"

            if len(payment_details) > 1:
                # Detalha cada pagamento se houver mais de um
                for p in payment_details:
                    method_name = payment_method_map.get(p['method'], f"ID {p['method']}")
                    payment_str += f"  - {method_name}: R$ {Decimal(p['amount']):.2f}\n"
                payment_str += f"  - *Valor Total Pago:* R$ {total_paid:.2f}\n"
            elif payment_details:
                # Formato simples para pagamento único
                method_name = payment_method_map.get(payment_details[0]['method'], f"ID {payment_details[0]['method']}")
                payment_str += f"  - Forma: {method_name}\n"
                payment_str += f"  - Valor Pago: R$ {total_paid:.2f}\n"
            else:
                # Caso de fiado, onde a lista de pagamentos pode ser vazia
                payment_str += f"  - Forma: Fiado\n"

            if change_amount > 0:
                payment_str += f"  - Troco: R$ {change_amount:.2f}\n"

            # --- Montagem da Mensagem Final ---
            discount_str = ""
            if discount_value > 0:
                discount_str = f"*Desconto:* R$ {discount_value:.2f}\n"

            message = (
                f"✅ *VENDA REALIZADA* ✅\n\n"
                f"👤 *Cliente:* {customer_name}\n"
                f"🆔 *Pedido:* {display_sale_id}\n"
                f"🗓️ *Data/Hora:* {now_str}\n\n"
                f"📋 *ITENS*\n{items_str}\n"
                f"{payment_str}\n"
                f"{discount_str}"
                f"*TOTAL GERAL: R$ {total_amount:.2f}*"
            )
            
            return message

        except Exception as e:
            logging.error(f"Erro ao construir mensagem de venda detalhada: {e}", exc_info=True)
            return None

    def _get_notification_recipients(self) -> List[str]:
        """Retorna lista de destinatários para notificações, incluindo o grupo configurado."""
        # Pega destinatários individuais das configurações de notificação
        recipients = self.notification_settings.get('notification_recipients', [])

        # Incluir configuração global se existir (número do admin/gerente)
        try:
            import database as db
            global_number = db.load_setting('whatsapp_notification_number', '')
            if global_number and global_number not in recipients:
                recipients.append(global_number)
        except Exception as e:
            logging.error(f"Erro ao obter destinatário global do banco de dados: {e}", exc_info=True)

        # Incluir o ID do grupo de notificação, se configurado
        try:
            group_id = self.config.get('advanced.GROUP_NOTIFICATION_ID')
            if group_id and group_id.strip() and group_id not in recipients:
                recipients.append(group_id.strip())
        except Exception as e:
            logging.error(f"Erro ao obter ID do grupo de notificação da configuração: {e}", exc_info=True)

        # Remove duplicados para garantir que cada ID seja único
        return list(dict.fromkeys(recipients))



    def _get_store_name(self) -> str:
        """Obtém nome da loja."""
        try:
            import database as db
            config = db.load_config()
            return config.get('store', {}).get('name', 'PDV')
        except Exception as e:
            logging.debug(f"Erro ao obter nome da loja: {e}")
            return 'PDV'

    # Métodos para configuração das notificações
    def enable_sale_notifications(self, enabled: bool):
        """Habilita/desabilita notificações de vendas."""
        self.notification_settings['enable_sale_notifications'] = enabled
        self._save_notification_settings()

    def enable_cash_notifications(self, enabled: bool):
        """Habilita/desabilita notificações de caixa."""
        self.notification_settings['enable_cash_notifications'] = enabled
        self._save_notification_settings()

    def enable_low_stock_alerts(self, enabled: bool):
        """Habilita/desabilita alertas de estoque baixo."""
        self.notification_settings['enable_low_stock_alerts'] = enabled
        self._save_notification_settings()

    def add_recipient(self, phone_number: str):
        """Adiciona destinatário para notificações."""
        recipients = self.notification_settings.get('notification_recipients', [])
        if phone_number not in recipients:
            recipients.append(phone_number)
            self.notification_settings['notification_recipients'] = recipients
            self._save_notification_settings()

    def remove_recipient(self, phone_number: str):
        """Remove destinatário das notificações."""
        recipients = self.notification_settings.get('notification_recipients', [])
        if phone_number in recipients:
            recipients.remove(phone_number)
            self.notification_settings['notification_recipients'] = recipients
            self._save_notification_settings()

    def set_minimum_sale_value(self, value: float):
        """Define valor mínimo para notificações de vendas."""
        self.notification_settings['minimum_sale_value'] = value
        self._save_notification_settings()

    def notify_credit_created(self, credit_sale_id: int) -> bool:
        """Notifica a criação de uma nova venda a crédito (fiado)."""
        try:
            if not db.are_notifications_globally_enabled() or not self.notification_settings.get('enable_sale_notifications', False):
                return True

            details = db.get_credit_sale_details(credit_sale_id)
            if not details:
                return False

            now_str = datetime.now().strftime('%d/%m/%Y %H:%M')
            message = (
                f"📝 *NOVO FIADO REGISTRADO* 📝\n\n"
                f"*Cliente:* {details['customer_name']}\n"
                f"*Valor:* R$ {details['amount']:.2f}\n"
                f"*Data:* {now_str}\n"
                f"*Operador:* {details['username']}\n"
                f"*ID do Fiado:* {credit_sale_id}"
            )

            recipients = self._get_notification_recipients()
            success_count = 0
            for phone in recipients:
                result = self.manager.send_message(phone, message, message_type='system_automatic')
                if result.get('success'):
                    success_count += 1
            return success_count > 0
        except Exception as e:
            logging.error(f"Erro ao notificar criação de fiado: {e}", exc_info=True)
            return False

    def notify_credit_paid(self, credit_sale_id: int) -> bool:
        """Notifica quando um fiado é totalmente pago."""
        try:
            if not db.are_notifications_globally_enabled() or not self.notification_settings.get('enable_sale_notifications', False):
                return True

            details = db.get_credit_sale_details(credit_sale_id)
            if not details or details['status'] != 'paid':
                return False

            now_str = datetime.now().strftime('%d/%m/%Y %H:%M')
            message = (
                f"🎉 *FIADO QUITADO* 🎉\n\n"
                f"*Cliente:* {details['customer_name']}\n"
                f"*Valor Total Pago:* R$ {details['total_paid']:.2f}\n"
                f"*Data da Quitação:* {now_str}\n"
                f"*ID do Fiado:* {credit_sale_id}"
            )

            recipients = self._get_notification_recipients()
            success_count = 0
            for phone in recipients:
                result = self.manager.send_message(phone, message, message_type='system_automatic')
                if result.get('success'):
                    success_count += 1
            return success_count > 0
        except Exception as e:
            logging.error(f"Erro ao notificar quitação de fiado: {e}", exc_info=True)
            return False

    def get_settings(self) -> Dict[str, Any]:
        """Retorna configurações atuais."""
        return self.notification_settings.copy()

# Instância global
_sales_notifier_instance = None

def get_whatsapp_sales_notifier() -> WhatsAppSalesNotifier:
    """Retorna instância singleton do notificador de vendas."""
    global _sales_notifier_instance
    if _sales_notifier_instance is None:
        _sales_notifier_instance = WhatsAppSalesNotifier()
    return _sales_notifier_instance
