import logging
from config_manager import ConfigManager

class SupabaseAPIClient:
    """
    Cliente para comunicação com a API do Supabase.
    Gerencia a conexão e fornece métodos para operações básicas.
    Usa lazy initialization para não bloquear o startup.
    """

    def __init__(self):
        self.client = None
        self._initialized = False
        self.config_manager = ConfigManager()
        # NÃO inicializa aqui - usa lazy initialization

    def _initialize_client(self):
        """Inicializa o cliente Supabase com as credenciais da configuração (lazy)."""
        if self._initialized:
            return
        
        try:
            from supabase import create_client, Client
            
            config = self.config_manager.get_config()
            supabase_config = config.get("supabase", {})

            supabase_url = supabase_config.get("url")
            supabase_key = supabase_config.get("key")

            if not supabase_url or not supabase_key:
                logging.debug("SupabaseAPIClient: URL ou chave do Supabase não configuradas (isso é normal se não usar sync).")
                self.client = None
                self._initialized = True
                return

            self.client = create_client(supabase_url, supabase_key)
            logging.info("SupabaseAPIClient: Cliente Supabase inicializado com sucesso.")

        except Exception as e:
            logging.error(f"SupabaseAPIClient: Erro ao inicializar cliente Supabase: {e}")
            self.client = None
        finally:
            self._initialized = True

    def check_connection(self) -> bool:
        """
        Verifica se a conexão com o Supabase está funcionando.

        Returns:
            bool: True se a conexão estiver ok, False caso contrário.
        """
        self._initialize_client()  # Lazy init
        
        if not self.client:
            return False

        try:
            # Tenta fazer uma consulta simples para testar a conexão
            response = self.client.table('products').select('id').limit(1).execute()
            logging.info("SupabaseAPIClient: Conexão com Supabase verificada com sucesso.")
            return True

        except Exception as e:
            logging.error(f"SupabaseAPIClient: Falha na verificação de conexão: {e}")
            return False

    def get_client(self):
        """
        Retorna o cliente Supabase para operações diretas.
        Inicializa o cliente se ainda não foi inicializado (lazy init).

        Returns:
            Client: Cliente Supabase configurado.
        """
        self._initialize_client()  # Lazy init
        return self.client

    def reload_config(self):
        """Recarrega a configuração e reinicializa o cliente."""
        logging.info("SupabaseAPIClient: Recarregando configuração...")
        self._initialized = False
        self._initialize_client()


# Instância global do cliente API (não inicializa no import)
api_client_instance = SupabaseAPIClient()
