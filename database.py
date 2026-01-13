# database.py - Módulo Fachada (Facade)
# Este arquivo re-exporta funções do novo pacote 'data' para manter
# a compatibilidade com o resto da aplicação.

# Setup
import os
from data.connection import get_db_connection, DB_FILE
from datetime import date

# Repositórios
from data.admin_repository import *
from data.audit_repository import *
from data.cash_repository import *
from data.credit_repository import *
from data.group_repository import *
from data.inventory_repository import *
from data.payment_method_repository import *
from data.product_repository import *
from data.reports_repository import *
from data.sale_repository import *
from data.user_repository import *
from data.settings_repository import *

# Alias para compatibilidade
load_config = load_setting

# Funções que não se encaixam em outros módulos (se houver alguma restante)
# ...

def get_db_statistics():
    """
    Coleta estatísticas vitais do banco de dados para o comando /db_status.
    """
    stats = {
        'file_size_mb': 0.0,
        'today_sales_count': 0,
        'total_sales_count': 0,
        'total_products_count': 0,
        'total_customers_count': 0
    }

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # 1. Tamanho do Arquivo
        if os.path.exists(DB_FILE):
            file_size_bytes = os.path.getsize(DB_FILE)
            stats['file_size_mb'] = file_size_bytes / (1024 * 1024)

        # 2. Vendas Hoje
        today_str = date.today().strftime('%Y-%m-%d')
        cursor.execute("SELECT COUNT(id) FROM sales WHERE DATE(sale_date) = ?", (today_str,))
        stats['today_sales_count'] = cursor.fetchone()[0]

        # 3. Vendas Totais
        cursor.execute("SELECT COUNT(id) FROM sales")
        stats['total_sales_count'] = cursor.fetchone()[0]

        # 4. Produtos Cadastrados (ativos)
        cursor.execute("SELECT COUNT(id) FROM products WHERE is_deleted = 0 OR is_deleted IS NULL")
        stats['total_products_count'] = cursor.fetchone()[0]

        # 5. Clientes Cadastrados (ativos)
        cursor.execute("SELECT COUNT(id) FROM customers WHERE is_deleted = 0 OR is_deleted IS NULL")
        stats['total_customers_count'] = cursor.fetchone()[0]

    except Exception as e:
        import logging
        logging.error(f"Erro ao coletar estatísticas do DB: {e}", exc_info=True)
        # Retorna estatísticas parciais ou zeradas
        pass
    finally:
        conn.close()

    return stats
