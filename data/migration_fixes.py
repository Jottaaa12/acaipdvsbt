import sqlite3
import logging
from data.connection import get_db_connection

def check_and_fix_sync_columns():
    """
    Verifica e corrige automaticamente problemas de migração parcial da migração 0004.add-sync-columns.sql.

    Esta função deve ser executada na inicialização do programa, logo após a verificação do yoyo,
    para consertar automaticamente o banco de dados de qualquer usuário que tenha tido essa migração parcial.
    """
    logging.info("Iniciando verificação de correção das colunas de sincronização...")

    # Lista de tabelas que deveriam ter sido atualizadas pela migração
    tables_to_check = [
        'product_groups',
        'products',
        'payment_methods',
        'users',
        'customers',
        'sales',
        'sale_items',
        'credit_sales',
        'credit_payments',
        'estoque_grupos',
        'estoque_itens',
        'cash_sessions'
    ]

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        corrections_made = 0

        for table in tables_to_check:
            try:
                # Verifica se a coluna sync_status já existe
                cursor.execute(f"PRAGMA table_info({table})")
                columns = cursor.fetchall()
                column_names = [col['name'] for col in columns]

                if 'sync_status' not in column_names:
                    logging.warning(f"Aplicando correção manual para tabela '{table}' - coluna sync_status não encontrada")

                    # Aplica as correções manuais conforme a migração original
                    try:
                        cursor.execute(f"ALTER TABLE {table} ADD COLUMN id_web TEXT")
                    except sqlite3.OperationalError as e:
                        if "duplicate column" in str(e).lower():
                            logging.debug(f"Coluna id_web já existe na tabela {table}")
                        else:
                            raise

                    try:
                        cursor.execute(f"CREATE UNIQUE INDEX IF NOT EXISTS idx_{table}_id_web_unique ON {table}(id_web)")
                    except sqlite3.OperationalError as e:
                        if "already another table or index with this name" in str(e).lower():
                            logging.debug(f"Índice idx_{table}_id_web_unique já existe")
                        else:
                            raise

                    try:
                        cursor.execute(f"ALTER TABLE {table} ADD COLUMN sync_status TEXT NOT NULL DEFAULT 'pending_create'")
                    except sqlite3.OperationalError as e:
                        if "duplicate column" in str(e).lower():
                            logging.debug(f"Coluna sync_status já existe na tabela {table}")
                        else:
                            raise

                    try:
                        cursor.execute(f"ALTER TABLE {table} ADD COLUMN last_modified_at TIMESTAMP")
                    except sqlite3.OperationalError as e:
                        if "duplicate column" in str(e).lower():
                            logging.debug(f"Coluna last_modified_at já existe na tabela {table}")
                        else:
                            raise

                    # Atualiza last_modified_at para registros existentes
                    cursor.execute(f"UPDATE {table} SET last_modified_at = CURRENT_TIMESTAMP WHERE last_modified_at IS NULL")

                    # Commit após cada tabela corrigida
                    conn.commit()
                    corrections_made += 1
                    logging.info(f"Correção aplicada com sucesso para tabela '{table}'")
                else:
                    logging.debug(f"Tabela '{table}' já possui coluna sync_status")

            except sqlite3.OperationalError as e:
                logging.error(f"Erro ao verificar/corrigir tabela '{table}': {e}")
                # Continua para a próxima tabela mesmo se houver erro
                continue

        if corrections_made > 0:
            logging.info(f"Verificação concluída. {corrections_made} tabelas foram corrigidas.")
        else:
            logging.info("Verificação concluída. Nenhuma correção foi necessária.")

    except Exception as e:
        logging.error(f"Erro geral durante verificação de correção das colunas de sincronização: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()
