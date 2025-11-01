import logging
from supabase import create_client, Client
from config_manager import ConfigManager

class SupabaseAPIClient:
    """
    Cliente para comunicação com a API do Supabase.
    Gerencia a conexão e fornece métodos para operações básicas.
    """

    def __init__(self):
        self.client: Client = None
        self.config_manager = ConfigManager()
        self._initialize_client()

    def _initialize_client(self):
        """Inicializa o cliente Supabase com as credenciais da configuração."""
        try:
            config = self.config_manager.get_config()
            supabase_config = config.get("supabase", {})

            supabase_url = supabase_config.get("url")
            supabase_key = supabase_config.get("key")

            if not supabase_url or not supabase_key:
                logging.warning("SupabaseAPIClient: URL ou chave do Supabase não encontradas na configuração.")
                self.client = None
                return

            self.client = create_client(supabase_url, supabase_key)
            logging.info("SupabaseAPIClient: Cliente Supabase inicializado com sucesso.")

        except Exception as e:
            logging.error(f"SupabaseAPIClient: Erro ao inicializar cliente Supabase: {e}")
            self.client = None

    def check_connection(self) -> bool:
        """
        Verifica se a conexão com o Supabase está funcionando.

        Returns:
            bool: True se a conexão estiver ok, False caso contrário.
        """
        if not self.client:
            logging.warning("SupabaseAPIClient: Cliente não inicializado.")
            return False

        try:
            # Tenta fazer uma consulta simples para testar a conexão
            response = self.client.table('products').select('id').limit(1).execute()
            logging.info("SupabaseAPIClient: Conexão com Supabase verificada com sucesso.")
            return True

        except Exception as e:
            logging.error(f"SupabaseAPIClient: Falha na verificação de conexão: {e}")
            return False

    def get_client(self) -> Client:
        """
        Retorna o cliente Supabase para operações diretas.

        Returns:
            Client: Cliente Supabase configurado.
        """
        return self.client

    def reload_config(self):
        """Recarrega a configuração e reinicializa o cliente."""
        logging.info("SupabaseAPIClient: Recarregando configuração...")
        self._initialize_client()


# Instância global do cliente API
api_client_instance = SupabaseAPIClient()
