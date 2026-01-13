"""
Configuração externa para parâmetros WhatsApp.
Gerencia timeouts, templates, validações e outras configurações.
"""
import json
import os
import re
from typing import Dict, Any, Optional, List
import logging

try:
    from utils import get_data_path
except Exception:
    def get_data_path(name: str) -> str:
        return os.path.join(os.getcwd(), name)

class WhatsAppConfig:
    """
    Gerenciador de configurações externas para WhatsApp.
    """

    # Valores padrão
    DEFAULT_CONFIG = {
        'connection': {
            'max_reconnect_attempts': 10,
            'base_reconnect_delay': 1.0,  # segundos
            'max_reconnect_delay': 300.0,  # 5 minutos
            'backoff_multiplier': 2.0,
            'connection_timeout': 30.0,
            'health_check_interval': 60.0,  # verificar saúde a cada minuto
            'session_expiry_days': 30,
        },
        'messages': {
            'max_message_length': 4096,
            'template_variables': {
                'store_name': '{store_name}',
                'customer_name': '{customer_name}',
                'total_amount': '{total_amount}',
                'order_number': '{order_number}',
                'date': '{date}',
                'time': '{time}',
            },
            'default_templates': {
                'sale_notification': '✅ *{store_name}*\n\nPedido realizado com sucesso!\n\n📋 *Número do pedido:* {order_number}\n💰 *Valor total:* R$ {total_amount}\n📅 *Data:* {date} {time}\n\nObrigado pela preferência!',
                'payment_reminder': '💰 *{store_name}*\n\nOlá {customer_name}!\n\nLembramos que há um pagamento pendente no valor de R$ {total_amount}.\n\nPor favor, regularize sua situação.',
                'welcome_message': '👋 Olá {customer_name}!\n\nBem-vindo ao *{store_name}*!',
                'cash_opening': '✅ *CAIXA ABERTO*\n\n📅 Data/Hora: {date} {time}\n👤 Operador: {operator}\n💰 Fundo de Troco: R$ {initial_amount}\n🆔 Sessão: #{session_id}\n\nCaixa aberto com sucesso!',
                'cash_closing': '❌ *CAIXA FECHADO*\n\n📅 Data/Hora: {date} {time}\n👤 Operador: {operator}\n💰 Saldo Inicial: R$ {initial_amount}\n💰 Total de Vendas: R$ {total_sales}\n💵 Dinheiro: R$ {cash_sales}\n💳 Cartão: R$ {card_sales}\n📱 PIX: R$ {pix_sales}\n💰 Valor Contado: R$ {final_amount}{difference_alert}\n🆔 Sessão: #{session_id}\n\nCaixa fechado com sucesso!',
                'detailed_sale_notification': '✅ *{store_name}*\n\n🛒 *VENDA REALIZADA*\n\n👤 Cliente: {customer_name}\n📋 Pedido: #{order_number}\n💰 Total: R$ {total_amount}\n\n💳 *Formas de Pagamento:*\n{payment_breakdown}\n\n📅 {date} às {time}\n\nObrigado pela preferência! 🍦',
                'low_stock_alert': '⚠️ *ALERTA DE ESTOQUE BAIXO*\n\n📦 Produto: {product_name}\n📊 Estoque Atual: {current_stock}\n📉 Estoque Mínimo: {min_stock}\n\nRefaça o pedido urgente!',
                'system_maintenance': '🔧 *MANUTENÇÃO DO SISTEMA*\n\nO PDV estará em manutenção das {start_time} às {end_time}.\n\nDurante este período o atendimento poderá ser interrompido.\n\nAgradecemos a compreensão!',
            },
        },
        'validation': {
            'phone_regex': r'^(\+55|55)?[\s\-\.]?\(?[1-9][0-9]\)?[\s\-\.]?[9]?[0-9]{4}[\s\-\.]?[0-9]{4}$',
            'require_country_code': True,
            'allowed_countries': ['BR'],
            'max_phone_verification_cache': 1000,
            'phone_verification_ttl_hours': 24,
        },
        'rate_limiting': {
            'max_messages_per_minute': 10,
            'max_messages_per_hour': 100,
            'burst_limit': 5,
            'enable_rate_limiting': True,
            'max_system_messages_per_minute': 5,
            'max_system_messages_per_hour': 50,
            'system_burst_limit': 3,
        },
        'monitoring': {
            'enable_health_checks': True,
            'log_all_messages': True,
            'enable_message_history': True,
            'max_history_entries': 10000,
        },
        'ui': {
            'status_update_interval': 2.0,  # segundos
            'qr_code_timeout': 300,  # 5 minutos
            'show_detailed_errors': True,
            'friendly_error_messages': {
                'connection_failed': 'Não foi possível conectar ao WhatsApp. Por favor, verifique sua conexão com a internet.',
                'invalid_number': 'O número de telefone informado não é válido ou não existe no WhatsApp.',
                'rate_limited': 'Muitas mensagens foram enviadas recentemente. Aguarde alguns minutos antes de tentar novamente.',
                'session_expired': 'A sessão do WhatsApp expirou. É necessário escanear o QR Code novamente.',
                'message_failed': 'Não foi possível enviar a mensagem. Verifique se o número está correto.',
            },
        },
        'paths': {
            'session_dir': 'whatsapp_session',
            'log_file': 'whatsapp.log',
            'message_log_file': 'whatsapp_messages.log',
            'cache_file': 'whatsapp_cache.json',
            'history_file': 'whatsapp_history.json',
        },
        'advanced': {
            'enable_debug_mode': False,
            'custom_user_agent': 'PDV-Desktop',
            'proxy_settings': None,
            'custom_baileys_version': None,
            'GROUP_NOTIFICATION_ID': '', # ID do grupo para notificações. Ex: "1234567890@g.us"
        }
    }

    def __init__(self, config_file: Optional[str] = None):
        self.config_file = config_file or get_data_path('whatsapp_config.json')
        self.config = self._load_config()
        self._validate_config()

    def _load_config(self) -> Dict[str, Any]:
        """Carrega configuração do arquivo ou usa defaults."""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    user_config = json.load(f)
                    return self._merge_configs(self.DEFAULT_CONFIG, user_config)
            except (json.JSONDecodeError, IOError) as e:
                logging.warning(f"Erro ao carregar config WhatsApp: {e}. Usando configurações padrão.")
                return self.DEFAULT_CONFIG.copy()
        else:
            return self.DEFAULT_CONFIG.copy()

    def _merge_configs(self, default: Dict[str, Any], user: Dict[str, Any]) -> Dict[str, Any]:
        """Mescla configuração do usuário com defaults recursivamente."""
        merged = default.copy()
        for key, value in user.items():
            if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
                merged[key] = self._merge_configs(merged[key], value)
            else:
                merged[key] = value
        return merged

    def _validate_config(self):
        """Valida configurações carregadas."""
        # Validar regex do telefone
        try:
            re.compile(self.config['validation']['phone_regex'])
        except re.error:
            logging.warning("Regex de telefone inválido. Usando padrão BR.")
            self.config['validation']['phone_regex'] = self.DEFAULT_CONFIG['validation']['phone_regex']

        # Garantir limites mínimos/máximos
        self.config['connection']['max_reconnect_attempts'] = max(1, min(50, self.config['connection']['max_reconnect_attempts']))
        self.config['connection']['base_reconnect_delay'] = max(0.1, min(10.0, self.config['connection']['base_reconnect_delay']))
        self.config['connection']['max_reconnect_delay'] = max(60.0, min(3600.0, self.config['connection']['max_reconnect_delay']))

    def save_config(self):
        """Salva configuração atual no arquivo."""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=4, ensure_ascii=False)
        except IOError as e:
            raise IOError(f"Não foi possível salvar configuração: {e}")

    def get(self, key_path: str, default: Any = None) -> Any:
        """Obtém valor de configuração usando caminho separado por pontos."""
        keys = key_path.split('.')
        value = self.config
        try:
            for key in keys:
                value = value[key]
            return value
        except (KeyError, TypeError):
            return default

    def set(self, key_path: str, value: Any):
        """Define valor de configuração usando caminho separado por pontos."""
        keys = key_path.split('.')
        config_ref = self.config
        for key in keys[:-1]:
            if key not in config_ref:
                config_ref[key] = {}
            config_ref = config_ref[key]
        config_ref[keys[-1]] = value

    def validate_phone(self, phone: str) -> Dict[str, Any]:
        """
        Valida e normaliza um número de telefone ou JID do WhatsApp.

        Returns:
            {
                'valid': bool,
                'normalized': str or None (retorna o JID completo),
                'error': str or None
            }
        """
        result = {'valid': False, 'normalized': None, 'error': None}
        if not phone:
            result['error'] = 'Número de telefone não pode ser vazio'
            return result

        phone_str = str(phone).strip()

        # Se for um ID de grupo, consideramos válido e retornamos como está.
        if phone_str.endswith('@g.us'):
            result['valid'] = True
            result['normalized'] = phone_str
            return result
            
        # Se for um LID (Linked Device ID), também consideramos válido como está.
        if 'lid' in phone_str.lower() or phone_str.endswith('@lid'):
            result['valid'] = True
            result['normalized'] = phone_str
            return result

        # Para outros JIDs (ex: @s.whatsapp.net, @lid), extraímos a parte numérica
        number_part = phone_str.split('@')[0]
        
        # Normalizar (remover tudo que não for dígito)
        normalized = re.sub(r'[^\d]', '', number_part)

        if not normalized:
            result['error'] = 'Formato de telefone inválido (sem dígitos)'
            return result

        # Adicionar DDI do Brasil se não estiver presente
        if not normalized.startswith('55'):
            normalized = '55' + normalized
        
        # Isolar o número sem o DDI para checar o 9º dígito
        number_without_cc = normalized[2:]
        
        # Adicionar o nono dígito se for um celular brasileiro e não o tiver
        if 11 <= int(number_without_cc[:2]) <= 99 and len(number_without_cc) == 10:
            number_without_cc = number_without_cc[:2] + '9' + number_without_cc[2:]

        # Remontar o JID completo com o sufixo padrão do WhatsApp
        final_jid = '55' + number_without_cc + '@s.whatsapp.net'

        result['valid'] = True
        result['normalized'] = final_jid
        return result

    def get_template(self, template_name: str) -> Optional[str]:
        """Retorna template de mensagem pelo nome."""
        return self.config['messages']['default_templates'].get(template_name)

    def get_friendly_error_message(self, error_key: str) -> str:
        """Retorna mensagem de erro amigável."""
        return self.config['ui']['friendly_error_messages'].get(error_key, error_key)

    def is_rate_limited(self, current_messages: int, time_window_minutes: int = 1) -> bool:
        """Verifica se está dentro dos limites de taxa."""
        if not self.config['rate_limiting']['enable_rate_limiting']:
            return False

        if time_window_minutes == 1:
            max_allowed = self.config['rate_limiting']['max_messages_per_minute']
        elif time_window_minutes == 60:
            max_allowed = self.config['rate_limiting']['max_messages_per_hour']
        else:
            return False

        return current_messages >= max_allowed

    def get_path(self, path_key: str) -> str:
        """Retorna caminho absoluto para arquivo WhatsApp."""
        relative_path = self.config['paths'].get(path_key)
        if relative_path:
            return get_data_path(relative_path)
        return get_data_path(f'whatsapp_{path_key}')

    def get_backoff_delay(self, attempt: int) -> float:
        """Calcula delay de backoff exponencial para reconexão."""
        base_delay = self.config['connection']['base_reconnect_delay']
        max_delay = self.config['connection']['max_reconnect_delay']
        multiplier = self.config['connection']['backoff_multiplier']

        delay = base_delay * (multiplier ** (attempt - 1))
        return min(delay, max_delay)

# Instância global de configuração
_config_instance = None

def get_whatsapp_config() -> WhatsAppConfig:
    """Retorna instância singleton da configuração WhatsApp."""
    global _config_instance
    if _config_instance is None:
        _config_instance = WhatsAppConfig()
    return _config_instance
