import os
import shutil
import sqlite3
from datetime import datetime
from .connection import get_db_connection, DB_FILE
from .audit_repository import log_audit
import logging

def delete_historical_data(user_id):
    """
    Exclui permanentemente todos os dados históricos de vendas, caixa e auditoria.
    Esta operação é IRREVERSÍVEL.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        conn.execute('BEGIN TRANSACTION')

        # Ordem de exclusão é importante devido a chaves estrangeiras
        cursor.execute('DELETE FROM sale_items')
        cursor.execute('DELETE FROM sale_payments')
        cursor.execute('DELETE FROM sales')
        cursor.execute('DELETE FROM cash_movements')
        cursor.execute('DELETE FROM cash_counts')
        cursor.execute('DELETE FROM cash_sessions')
        cursor.execute('DELETE FROM audit_log')

        conn.commit()
        log_audit(user_id, 'DELETE_HISTORICAL_DATA', 'ALL_HISTORICAL', None, new_values="Todos os dados históricos foram excluídos.")
        return True, "Dados históricos excluídos com sucesso."
    except sqlite3.Error as e:
        conn.rollback()
        logging.error(f"Erro ao excluir dados históricos: {e}", exc_info=True)
        return False, f"Erro de banco de dados ao excluir dados históricos: {e}"
    finally:
        conn.close()

def create_backup():
    """Cria backup do banco de dados."""
    if not os.path.exists(DB_FILE):
        return False, "Banco de dados não encontrado"
    
    backup_dir = 'backups'
    if not os.path.exists(backup_dir):
        os.makedirs(backup_dir)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_file = os.path.join(backup_dir, f'pdv_backup_{timestamp}.db')
    
    try:
        shutil.copy2(DB_FILE, backup_file)
        return True, backup_file
    except Exception as e:
        return False, str(e)

def restore_backup(backup_file):
    """Restaura backup do banco de dados."""
    if not os.path.exists(backup_file):
        return False, "Arquivo de backup não encontrado"
    
    try:
        # Faz backup do atual antes de restaurar
        current_backup = f'{DB_FILE}.backup_before_restore'
        shutil.copy2(DB_FILE, current_backup)
        
        # Restaura o backup
        shutil.copy2(backup_file, DB_FILE)
        return True, "Backup restaurado com sucesso"
    except Exception as e:
        return False, str(e)

def list_backups():
    """Lista todos os backups disponíveis."""
    backup_dir = 'backups'
    if not os.path.exists(backup_dir):
        return []
    
    backups = []
    for file in os.listdir(backup_dir):
        if file.startswith('pdv_backup_') and file.endswith('.db'):
            file_path = os.path.join(backup_dir, file)
            stat = os.stat(file_path)
            backups.append({
                'filename': file,
                'path': file_path,
                'size': stat.st_size,
                'created': datetime.fromtimestamp(stat.st_ctime)
            })
    
    return sorted(backups, key=lambda x: x['created'], reverse=True)
