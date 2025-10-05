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
            "hardware_mode": "production",  # Inicia em modo de produção por padrão
            "scale": {
                "port": "COM3",
                "baudrate": 9600,
                "protocol": "toledo_mgv6"
            },
            "printer": {
                "type": "usb",
                "vendor_id": "0x04b8",
                "product_id": "0x0e28",
                "name": "EPSON TM-T20X"
            },
            "establishment": {
                "name": "Nome do Estabelecimento",
                "address": "Endereço do Estabelecimento",
                "phone": "(99) 99999-9999"
            },
            "whatsapp": {
                "enabled": False,
                "notifications": {
                    "sales": False,
                    "cash_closing": False
                }
            }
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
