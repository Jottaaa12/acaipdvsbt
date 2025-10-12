
import sqlite3
import logging
from database import get_db_connection

# --- Funções de Gerenciamento de Grupos de Estoque ---

def add_stock_group(name):
    """Adiciona um novo grupo de estoque."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('INSERT INTO estoque_grupos (nome) VALUES (?)', (name,))
        conn.commit()
        return True, cursor.lastrowid
    except sqlite3.IntegrityError:
        return False, "Erro: Já existe um grupo com este nome."
    except sqlite3.Error as e:
        return False, f"Erro de banco de dados: {e}"
    finally:
        conn.close()

def get_all_stock_groups():
    """Retorna todos os grupos de estoque."""
    conn = get_db_connection()
    groups = conn.execute('SELECT * FROM estoque_grupos ORDER BY nome').fetchall()
    conn.close()
    return [dict(row) for row in groups]

def update_stock_group(group_id, name):
    """Atualiza o nome de um grupo de estoque."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('UPDATE estoque_grupos SET nome = ? WHERE id = ?', (name, group_id))
        conn.commit()
        return True, "Grupo atualizado com sucesso."
    except sqlite3.IntegrityError:
        return False, "Erro: Já existe um grupo com este nome."
    except sqlite3.Error as e:
        return False, f"Erro de banco de dados: {e}"
    finally:
        conn.close()

def delete_stock_group(group_id):
    """Deleta um grupo de estoque se não houver itens associados."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Verifica se o grupo está sendo usado por algum item
        cursor.execute('SELECT COUNT(*) FROM estoque_itens WHERE grupo_id = ?', (group_id,))
        item_count = cursor.fetchone()[0]
        if item_count > 0:
            return False, f"Não é possível deletar o grupo, pois ele contém {item_count} item(ns)."

        cursor.execute('DELETE FROM estoque_grupos WHERE id = ?', (group_id,))
        conn.commit()
        if cursor.rowcount > 0:
            return True, "Grupo deletado com sucesso."
        return False, "Grupo não encontrado."
    except sqlite3.Error as e:
        conn.rollback()
        return False, f"Erro de banco de dados: {e}"
    finally:
        conn.close()

# --- Funções de Gerenciamento de Itens de Estoque ---

def add_stock_item(codigo, nome, grupo_id, estoque_atual, estoque_minimo, unidade_medida):
    """Adiciona um novo item de estoque."""
    logging.info(f"Tentando adicionar item de estoque com os seguintes dados: codigo={codigo}, nome={nome}, grupo_id={grupo_id}, estoque_atual={estoque_atual}, estoque_minimo={estoque_minimo}, unidade_medida={unidade_medida}")
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Etapa de depuração 2: Verifica se o grupo_id existe na tabela de grupos
        cursor.execute("SELECT id FROM estoque_grupos WHERE id = ?", (grupo_id,))
        if not cursor.fetchone():
            return False, f"Erro de Chave Estrangeira: O grupo com ID '{grupo_id}' não foi encontrado na tabela de grupos."

        # Etapa de depuração 1: Verifica se o código já existe
        cursor.execute("SELECT id FROM estoque_itens WHERE codigo = ?", (codigo,))
        existing_item = cursor.fetchone()
        if existing_item:
            return False, f"Erro de depuração: O código '{codigo}' já está em uso pelo item de ID {existing_item['id']}."

        cursor.execute(
            'INSERT INTO estoque_itens (codigo, nome, grupo_id, estoque_atual, estoque_minimo, unidade_medida) VALUES (?, ?, ?, ?, ?, ?)',
            (codigo, nome, grupo_id, estoque_atual, estoque_minimo, unidade_medida)
        )
        conn.commit()
        return True, cursor.lastrowid
    except sqlite3.IntegrityError as e:
        logging.error(f"RAW SQLITE ERROR: {e!r}") # Log do erro puro
        return False, f"Erro de Banco de Dados: {e}"
    except sqlite3.Error as e:
        return False, f"Erro de banco de dados: {e}"
    finally:
        conn.close()

def get_all_stock_items():
    """Retorna todos os itens de estoque, com o nome do grupo."""
    conn = get_db_connection()
    query = '''
        SELECT 
            i.id, i.codigo, i.nome, i.grupo_id, i.estoque_atual, 
            i.estoque_minimo, i.unidade_medida, g.nome as grupo_nome
        FROM estoque_itens i
        LEFT JOIN estoque_grupos g ON i.grupo_id = g.id
        ORDER BY g.nome, i.nome
    '''
    items = conn.execute(query).fetchall()
    conn.close()
    return [dict(row) for row in items]

def get_item_by_code(codigo):
    """Busca um item de estoque pelo seu código."""
    conn = get_db_connection()
    item = conn.execute('SELECT * FROM estoque_itens WHERE codigo = ?', (codigo,)).fetchone()
    conn.close()
    return dict(item) if item else None

def update_stock_item(item_id, codigo, nome, grupo_id, estoque_atual, estoque_minimo, unidade_medida):
    """Atualiza os dados de um item de estoque."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            UPDATE estoque_itens
            SET codigo = ?, nome = ?, grupo_id = ?, estoque_atual = ?, estoque_minimo = ?, unidade_medida = ?
            WHERE id = ?
        ''', (codigo, nome, grupo_id, estoque_atual, estoque_minimo, unidade_medida, item_id))
        conn.commit()
        return True, "Item atualizado com sucesso."
    except sqlite3.IntegrityError:
        return False, "Erro: O código informado já pertence a outro item."
    except sqlite3.Error as e:
        return False, f"Erro de banco de dados: {e}"
    finally:
        conn.close()

def delete_stock_item(item_id):
    """Deleta um item de estoque."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('DELETE FROM estoque_itens WHERE id = ?', (item_id,))
        conn.commit()
        if cursor.rowcount > 0:
            return True, "Item deletado com sucesso."
        return False, "Item não encontrado."
    except sqlite3.Error as e:
        return False, f"Erro de banco de dados: {e}"
    finally:
        conn.close()

def adjust_stock_quantity(item_codigo, nova_quantidade):
    """Ajusta o estoque de um item para um valor específico."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('UPDATE estoque_itens SET estoque_atual = ? WHERE codigo = ?', (nova_quantidade, item_codigo))
        conn.commit()
        if cursor.rowcount > 0:
            return True, "Estoque ajustado com sucesso."
        return False, "Item com o código não encontrado."
    except sqlite3.Error as e:
        return False, f"Erro de banco de dados: {e}"
    finally:
        conn.close()

def give_stock_out(item_codigo, quantidade):
    """Dá baixa em uma quantidade do estoque de um item."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Usar COALESCE para tratar estoque NULL, embora não deva acontecer
        cursor.execute(
            'UPDATE estoque_itens SET estoque_atual = COALESCE(estoque_atual, 0) - ? WHERE codigo = ?',
            (quantidade, item_codigo)
        )
        conn.commit()
        if cursor.rowcount > 0:
            return True, f"{quantidade} unidade(s) baixada(s) do estoque."
        return False, "Item com o código não encontrado."
    except sqlite3.Error as e:
        return False, f"Erro de banco de dados: {e}"
    finally:
        conn.close()
