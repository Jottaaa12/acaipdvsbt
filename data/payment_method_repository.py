import sqlite3
from .connection import get_db_connection

def add_payment_method(name):
    """Adiciona uma nova forma de pagamento."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('INSERT INTO payment_methods (name) VALUES (?)', (name,))
        conn.commit()
        return True, cursor.lastrowid
    except sqlite3.IntegrityError:
        return False, "Erro: Já existe uma forma de pagamento com este nome."
    except sqlite3.Error as e:
        return False, f"Erro de banco de dados ao adicionar forma de pagamento: {e}"
    finally:
        conn.close()

def get_all_payment_methods():
    conn = get_db_connection()
    methods = conn.execute('SELECT * FROM payment_methods WHERE is_deleted = 0 ORDER BY name').fetchall()
    conn.close()
    return methods

def update_payment_method(method_id, name):
    """Atualiza o nome de uma forma de pagamento."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('UPDATE payment_methods SET name = ?, sync_status = CASE WHEN sync_status = \'pending_create\' THEN \'pending_create\' ELSE \'pending_update\' END WHERE id = ?', (name, method_id))
        conn.commit()
        return True, "Forma de pagamento atualizada com sucesso."
    except sqlite3.IntegrityError:
        return False, "Erro: Já existe uma forma de pagamento com este nome."
    except sqlite3.Error as e:
        return False, f"Erro de banco de dados ao atualizar forma de pagamento: {e}"
    finally:
        conn.close()

def delete_payment_method(method_id):
    """Marca uma forma de pagamento como deletada (soft delete)."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""UPDATE payment_methods SET is_deleted = 1, sync_status = 'pending_update' WHERE id = ?""", (method_id,))
        conn.commit()
        
        if cursor.rowcount > 0:
            return True, "Forma de pagamento deletada com sucesso."
        return False, "Forma de pagamento não encontrada."

    except sqlite3.Error as e:
        conn.rollback()
        return False, f"Erro de banco de dados ao deletar forma de pagamento: {e}"
    finally:
        conn.close()
