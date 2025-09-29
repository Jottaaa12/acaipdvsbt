"""
Sistema de notificações automáticas de vendas via WhatsApp.
Integra com o sistema de vendas para enviar notificações quando vendas são realizadas.
"""
import json
import os
from typing import Dict, List, Optional, Any
from datetime import datetime
from decimal import Decimal

from .whatsapp_manager import WhatsAppManager
from .whatsapp_config import get_whatsapp_config
from utils import get_data_path

class WhatsAppSalesNotifier:
    """
    Notificador de vendas que envia mensagens automáticas via WhatsApp.
    """

    def __init__(self):
        self.manager = WhatsAppManager.get_instance()
        self.config = get_whatsapp_config()
        self._notification_settings_path = get_data_path('whatsapp_sales_notifications.json')
        self._load_notification_settings()

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
            print(f"Erro ao carregar configurações de notificações: {e}")
            self.notification_settings = self._get_default_settings()

    def _save_notification_settings(self):
        """Salva configurações de notificações."""
        try:
            with open(self._notification_settings_path, 'w', encoding='utf-8') as f:
                json.dump(self.notification_settings, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"Erro ao salvar configurações de notificações: {e}")

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

    def notify_sale(self, sale_data: Dict[str, Any], payment_details: List[Dict[str, Any]]) -> bool:
        """
        Notifica uma venda realizada.

        Args:
            sale_data: Dados da venda (id, customer_name, total_amount, etc.)
            payment_details: Lista de pagamentos com método e valor

        Returns:
            bool: True se notificou com sucesso
        """
        try:
            # Verificar se notificações estão habilitadas
            if not self.notification_settings.get('enable_sale_notifications', False):
                return True

            # Verificar valor mínimo
            min_value = self.notification_settings.get('minimum_sale_value', 0.0)
            if float(sale_data.get('total_amount', 0)) < min_value:
                return True

            # Verificar delay entre notificações
            delay = self.notification_settings.get('notification_delay', 0)
            if delay > 0 and not self._can_send_notification(delay):
                return True

            # Construir mensagem detalhada
            message = self._build_sale_message(sale_data, payment_details)

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
                        print(f"Falha ao enviar notificação para {phone}: {result.get('error')}")
                except Exception as e:
                    print(f"Erro ao enviar notificação para {phone}: {e}")

            # Registrar hora da última notificação
            self.notification_settings['last_notification_times']['sale'] = datetime.now().isoformat()
            self._save_notification_settings()

            return success_count > 0

        except Exception as e:
            print(f"Erro ao notificar venda: {e}")
            return False

    def notify_cash_opening(self, session_data: Dict[str, Any]) -> bool:
        """Notifica abertura de caixa."""
        try:
            if not self.notification_settings.get('enable_cash_notifications', False):
                return True

            template = self.config.get_template('cash_opening')
            message = template.format(
                date=datetime.now().strftime('%d/%m/%Y'),
                time=datetime.now().strftime('%H:%M'),
                operator=session_data.get('username', 'Sistema'),
                initial_amount=float(session_data.get('initial_amount', 0)),
                session_id=session_data.get('id', 0)
            )

            recipients = self._get_notification_recipients()
            success_count = 0

            for phone in recipients:
                result = self.manager.send_message(phone, message, message_type='system_automatic')
                if result.get('success'):
                    success_count += 1

            return success_count > 0

        except Exception as e:
            print(f"Erro ao notificar abertura de caixa: {e}")
            return False

    def notify_cash_closing(self, session_data: Dict[str, Any], sales_summary: List[Dict[str, Any]]) -> bool:
        """Notifica fechamento de caixa com totais por forma de pagamento."""
        try:
            if not self.notification_settings.get('enable_cash_notifications', False):
                return True

            # Calcular totais por forma de pagamento
            payment_totals = {}
            total_sales = Decimal('0')
            cash_sales = Decimal('0')
            card_sales = Decimal('0')
            pix_sales = Decimal('0')

            for sale in sales_summary:
                method = sale['payment_method']
                total = Decimal(str(sale.get('total', 0)))
                total_sales += total

                if method == 'Dinheiro':
                    cash_sales += total
                elif method in ['Débito', 'Crédito']:
                    card_sales += total
                elif method == 'PIX':
                    pix_sales += total

                payment_totals[method] = payment_totals.get(method, Decimal('0')) + total

            # Construir detalhamento das vendas
            sales_breakdown = ""
            if self.notification_settings.get('detailed_payment_breakdown', True) and payment_totals:
                sales_breakdown = "\n\n💰 *DETALHAMENTO DAS VENDAS:*"
                payment_icons = {
                    'Dinheiro': '💵',
                    'PIX': '📱',
                    'Débito': '💳',
                    'Crédito': '💳',
                }

                for method, total in payment_totals.items():
                    icon = payment_icons.get(method, '💰')
                    sales_breakdown += f"\n{icon} {method}: R$ {total:.2f}"

            # Construir alerta de diferença
            difference_alert = ""
            difference = session_data.get('difference', 0)
            if difference != 0:
                diff_symbol = "+" if difference > 0 else ""
                difference_alert = f"\n⚠️ Diferença: {diff_symbol}R$ {abs(difference):.2f}"

            template = self.config.get_template('cash_closing')
            message = template.format(
                date=datetime.now().strftime('%d/%m/%Y'),
                time=datetime.now().strftime('%H:%M'),
                operator=session_data.get('username', 'Sistema'),
                initial_amount=float(session_data.get('initial_amount', 0)),
                total_sales=float(total_sales),
                cash_sales=float(cash_sales),
                card_sales=float(card_sales),
                pix_sales=float(pix_sales),
                final_amount=float(session_data.get('final_amount', 0)),
                session_id=session_data.get('id', 0),
                difference_alert=difference_alert
            )

            if sales_breakdown:
                message = message.replace('\n🆔 Sessão', f'{sales_breakdown}\n🆔 Sessão')

            recipients = self._get_notification_recipients()
            success_count = 0

            for phone in recipients:
                result = self.manager.send_message(phone, message, message_type='system_automatic')
                if result.get('success'):
                    success_count += 1

            return success_count > 0

        except Exception as e:
            print(f"Erro ao notificar fechamento de caixa: {e}")
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
            print(f"Erro ao notificar estoque baixo: {e}")
            return False

    def _build_sale_message(self, sale_data: Dict[str, Any], payment_details: List[Dict[str, Any]]) -> Optional[str]:
        """Constrói mensagem detalhada de venda."""
        try:
            # Agrupar pagamentos por método
            payment_summary = {}
            for payment in payment_details:
                method = payment['method']
                amount = float(payment['amount'])
                payment_summary[method] = payment_summary.get(method, 0) + amount

            # Construir detalhamento dos pagamentos
            payment_breakdown = ""
            if self.notification_settings.get('detailed_payment_breakdown', True):
                payment_breakdown = "Formas de Pagamento:\n"
                payment_icons = {
                    'Dinheiro': '💵',
                    'PIX': '📱',
                    'Débito': '💳',
                    'Crédito': '💳',
                }

                for method, total in payment_summary.items():
                    icon = payment_icons.get(method, '💰')
                    payment_breakdown += f"  {icon} {method}: R$ {total:.2f}\n"

            payment_breakdown = payment_breakdown.rstrip()

            # Verificar se há template customizado
            custom_templates = self.notification_settings.get('custom_message_templates', {})
            template_name = custom_templates.get('sale_notification', 'detailed_sale_notification')

            template = self.config.get_template(template_name)
            if not template:
                template = self.config.get_template('detailed_sale_notification')

            message = template.format(
                store_name=self._get_store_name(),
                customer_name=sale_data.get('customer_name', 'Cliente'),
                order_number=sale_data.get('id', 'N/A'),
                total_amount=float(sale_data.get('total_amount', 0)),
                payment_breakdown=payment_breakdown,
                date=datetime.now().strftime('%d/%m/%Y'),
                time=datetime.now().strftime('%H:%M')
            )

            return message

        except Exception as e:
            print(f"Erro ao construir mensagem de venda: {e}")
            return None

    def _get_notification_recipients(self) -> List[str]:
        """Retorna lista de destinatários para notificações."""
        recipients = self.notification_settings.get('notification_recipients', [])

        # Incluir configuração global se existir
        try:
            import database as db
            global_number = db.load_setting('whatsapp_notification_number', '')
            if global_number and global_number not in recipients:
                recipients.append(global_number)
        except Exception as e:
            print(f"Erro ao obter destinatários globais: {e}")

        return recipients

    def _can_send_notification(self, delay_seconds: int) -> bool:
        """Verifica se pode enviar notificação baseado no delay."""
        try:
            last_time_str = self.notification_settings.get('last_notification_times', {}).get('sale')
            if not last_time_str:
                return True

            last_time = datetime.fromisoformat(last_time_str)
            time_diff = (datetime.now() - last_time).total_seconds()

            return time_diff >= delay_seconds

        except Exception as e:
            print(f"Erro ao verificar delay de notificação: {e}")
            return True

    def _get_store_name(self) -> str:
        """Obtém nome da loja."""
        try:
            import database as db
            config = db.load_config()
            return config.get('store', {}).get('name', 'PDV')
        except:
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
