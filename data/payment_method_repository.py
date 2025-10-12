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
    methods = conn.execute('SELECT * FROM payment_methods ORDER BY name').fetchall()
    conn.close()
    return methods

def update_payment_method(method_id, name):
    """Atualiza o nome de uma forma de pagamento."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('UPDATE payment_methods SET name = ? WHERE id = ?', (name, method_id))
        conn.commit()
        return True, "Forma de pagamento atualizada com sucesso."
    except sqlite3.IntegrityError:
        return False, "Erro: Já existe uma forma de pagamento com este nome."
    except sqlite3.Error as e:
        return False, f"Erro de banco de dados ao atualizar forma de pagamento: {e}"
    finally:
        conn.close()

def delete_payment_method(method_id):
    """Deleta uma forma de pagamento."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Verifica se a forma de pagamento está sendo usada em alguma venda na nova tabela sale_payments.
        usage_count = cursor.execute(
            'SELECT COUNT(*) FROM sale_payments WHERE payment_method = (SELECT name FROM payment_methods WHERE id = ?)',
            (method_id,)
        ).fetchone()[0]

        if usage_count > 0:
            return False, f"Esta forma de pagamento não pode ser deletada pois está associada a {usage_count} pagamento(s)."

        cursor.execute('DELETE FROM payment_methods WHERE id = ?', (method_id,))
        conn.commit()
        
        if cursor.rowcount > 0:
            return True, "Forma de pagamento deletada com sucesso."
        return False, "Forma de pagamento não encontrada."

    except sqlite3.Error as e:
        conn.rollback()
        return False, f"Erro de banco de dados ao deletar forma de pagamento: {e}"
    finally:
        conn.close()
