import json
import os
from utils import get_data_path

class ConfigManager:
    def __init__(self, filename='config.json'):
        """
        Gerenciador de configurações que armazena o arquivo em APPDATA.
        Cria uma configuração padrão se o arquivo não existir.
        """
        self.config_path = get_data_path(filename)
        self._config = self.load_config()

    def get_default_config(self):
        """Retorna a estrutura de configuração padrão para a primeira execução."""
        return {
            "store": {
                "name": "Acai sabor da terra",
                "address": "Endereço da Loja",
                "phone": "Telefone da Loja",
                "cnpj": "CNPJ da Loja"
            },
            "shortcuts": [
                {
                    "name": "acai 200g",
                    "barcode": "acai200"
                },
                {
                    "name": "acai 240g",
                    "barcode": "acai240"
                },
                {
                    "name": "acai 300g",
                    "barcode": "acai300"
                }
            ],
            "printer": {
                "type": "thermal_bluetooth",
                "usb_vendor_id": "",
                "usb_product_id": "",
                "bluetooth_port": "COM4",
                "serial_port": "",
                "serial_baudrate": 9600,
                "network_ip": "",
                "network_port": 9100,
                "auto_print_receipt": False
            },
            "hardware_mode": "production",
            "scale": {
                "port": "COM3",
                "baudrate": 4800,
                "bytesize": 8,
                "parity": "N",
                "stopbits": 1
            },
            "whatsapp": {
                "notification_number": "5588981905006"
            },
            "supabase": {
                "url": "https://clncykjzukfjxvqjbcgx.supabase.co",
                "key": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImNsbmN5a2p6dWtmanh2cWpiY2d4Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjE1NzUyNzcsImV4cCI6MjA3NzE1MTI3N30.UoHNsGHlmV0HQ1HHMyWRrqQiEQyups0CMefCeZ5zDKU"
            },
            "scheduled_notifications": []
        }

    def load_config(self):
        """
        Carrega a configuração do arquivo. Se o arquivo não existir ou estiver corrompido,
        cria um novo com os valores padrão.
        """
        if not os.path.exists(self.config_path):
            print(f"Arquivo de configuração não encontrado. Criando um novo em: {self.config_path}")
            default_config = self.get_default_config()
            self.save_config(default_config)
            return default_config
        
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            print(f"Erro ao ler o arquivo de configuração. Restaurando para o padrão.")
            default_config = self.get_default_config()
            self.save_config(default_config)
            return default_config

    def save_config(self, config_data):
        """Salva o dicionário de configuração no arquivo JSON."""
        self._config = config_data
        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, indent=4, ensure_ascii=False)

    def get_config(self):
        """Retorna a configuração carregada."""
        return self._config

    def get_section(self, section_name):
        """Retorna uma seção específica da configuração."""
        return self._config.get(section_name, {})

    def update_section(self, section_name, section_data):
        """Atualiza uma seção da configuração e salva o arquivo."""
        self._config[section_name] = section_data
        self.save_config(self._config)

    def get_scheduled_notifications(self):
        """Retorna a lista de notificações agendadas."""
        return self._config.get("scheduled_notifications", [])

    def add_scheduled_notification(self, notification_data):
        """Adiciona uma nova notificação agendada e salva a configuração."""
        notifications = self.get_scheduled_notifications()
        notifications.append(notification_data)
        self.update_section("scheduled_notifications", notifications)

    def update_scheduled_notification(self, notification_id, notification_data):
        """Atualiza uma notificação agendada existente pelo ID e salva a configuração."""
        notifications = self.get_scheduled_notifications()
        for i, notif in enumerate(notifications):
            if notif.get("id") == notification_id:
                notifications[i] = notification_data
                break
        self.update_section("scheduled_notifications", notifications)

    def delete_scheduled_notification(self, notification_id):
        """Remove uma notificação agendada pelo ID e salva a configuração."""
        notifications = self.get_scheduled_notifications()
        notifications = [notif for notif in notifications if notif.get("id") != notification_id]
        self.update_section("scheduled_notifications", notifications)

