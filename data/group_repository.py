import sqlite3
from .connection import get_db_connection

def add_group(name):
    """Adiciona um novo grupo de produtos."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('INSERT INTO product_groups (name) VALUES (?)', (name,))
        conn.commit()
        return True, cursor.lastrowid
    except sqlite3.IntegrityError:
        return False, "Erro: Já existe um grupo com este nome."
    except sqlite3.Error as e:
        return False, f"Erro de banco de dados ao adicionar grupo: {e}"
    finally:
        conn.close()

def get_all_groups():
    conn = get_db_connection()
    groups = conn.execute('SELECT * FROM product_groups ORDER BY name').fetchall()
    conn.close()
    return groups

def update_group(group_id, name):
    """Atualiza o nome de um grupo de produtos."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('UPDATE product_groups SET name = ?, sync_status = CASE WHEN sync_status = \'pending_create\' THEN \'pending_create\' ELSE \'pending_update\' END WHERE id = ?', (name, group_id))
        conn.commit()
        return True, "Grupo atualizado com sucesso."
    except sqlite3.IntegrityError:
        return False, "Erro: Já existe um grupo com este nome."
    except sqlite3.Error as e:
        return False, f"Erro de banco de dados ao atualizar grupo: {e}"
    finally:
        conn.close()

def delete_group(group_id):
    """Deleta um grupo, desassociando produtos primeiro."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Transação para garantir atomicidade
        cursor.execute('BEGIN')
        cursor.execute('UPDATE products SET group_id = NULL WHERE group_id = ?', (group_id,))
        cursor.execute('DELETE FROM product_groups WHERE id = ?', (group_id,))
        conn.commit()
        return True, "Grupo deletado com sucesso."
    except sqlite3.Error as e:
        conn.rollback()
        return False, f"Erro de banco de dados ao deletar grupo: {e}"
    finally:
        conn.close()
