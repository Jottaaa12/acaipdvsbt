
import os
from supabase import create_client, Client
from config_manager import ConfigManager

def main():
    """
    Testa a conexão com o Supabase.
    """
    try:
        # Carrega a configuração
        config_manager = ConfigManager()
        config = config_manager.get_config()
        
        # Obtém as credenciais do Supabase
        supabase_url = config.get("supabase", {}).get("url")
        supabase_key = config.get("supabase", {}).get("key")
        
        if not supabase_url or not supabase_key:
            print("URL ou chave do Supabase não encontradas no arquivo de configuração.")
            print("Por favor, adicione as credenciais no arquivo config.json e tente novamente.")
            return

        # Cria o cliente Supabase
        supabase: Client = create_client(supabase_url, supabase_key)
        
        # Testa a conexão
        response = supabase.table('products').select('id').limit(1).execute()
        
        print("Conexão com o Supabase bem-sucedida!")
        
    except Exception as e:
        print(f"Erro ao conectar com o Supabase: {e}")

if __name__ == "__main__":
    main()
