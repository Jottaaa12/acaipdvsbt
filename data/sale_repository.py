import sqlite3
import logging
from decimal import Decimal
from typing import Optional
from .connection import get_db_connection
from .audit_repository import log_audit
from utils import to_cents, to_reais

def register_sale(total_amount, payment_method, items):
    """[DEPRECATED] Registra uma venda. Use register_sale_with_user para novos desenvolvimentos."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        total_amount_cents = to_cents(total_amount)
        # Corrige problema de timezone: usa horário local
        from datetime import datetime
        sale_date_local = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute('INSERT INTO sales (sale_date, total_amount, payment_method) VALUES (?, ?, ?)', (sale_date_local, total_amount_cents, payment_method))
        sale_id = cursor.lastrowid
        for item in items:
            unit_price_cents = to_cents(item['unit_price'])
            total_price_cents = to_cents(item['total_price'])
            cursor.execute('INSERT INTO sale_items (sale_id, product_id, quantity, unit_price, total_price) VALUES (?, ?, ?, ?, ?)',
                           (sale_id, item['id'], item['quantity'], unit_price_cents, total_price_cents))
            
            # Apenas atualiza o estoque para itens vendidos por unidade.
            if item.get('sale_type') == 'unit':
                cursor.execute("UPDATE products SET stock = stock - ?, sync_status = CASE WHEN sync_status = 'pending_create' THEN 'pending_create' ELSE 'pending_update' END WHERE id = ?", (item['quantity'], item['id']))
        conn.commit()
    except sqlite3.Error as e:
        logging.error(f"Erro ao registrar a venda: {e}", exc_info=True)
        conn.rollback()
    finally:
        conn.close()

def get_all_sales():
    conn = get_db_connection()
    query = '''
        SELECT s.id, s.sale_date, s.total_amount, s.payment_method, u.username
        FROM sales s
        LEFT JOIN users u ON s.user_id = u.id
        ORDER BY s.sale_date DESC
    '''
    rows = conn.execute(query).fetchall()
    conn.close()
    sales = []
    for row in rows:
        sale = dict(row)
        if sale['total_amount'] is not None:
            sale['total_amount'] = to_reais(sale['total_amount'])
        sales.append(sale)
    return sales

def get_sales_by_period(start_date, end_date):
    """
    Retorna todas as vendas dentro de um período de datas específico.
    As datas devem estar no formato 'YYYY-MM-DD'.
    """
    conn = get_db_connection()
    
    # Adiciona o horário para pegar o dia inteiro
    start_datetime = f'{start_date} 00:00:00'
    end_datetime = f'{end_date} 23:59:59'
    
    query = '''
        SELECT s.*, u.username 
        FROM sales s
        LEFT JOIN users u ON s.user_id = u.id
        WHERE s.sale_date BETWEEN ? AND ?
        ORDER BY s.sale_date DESC
    '''
    
    rows = conn.execute(query, (start_datetime, end_datetime)).fetchall()
    conn.close()
    
    sales = []
    for row in rows:
        sale = dict(row)
        # Usa a função from_cents que já existe no seu utils.py
        sale['total_amount'] = to_reais(sale['total_amount'])
        sales.append(sale)
        
    return sales

def get_sales_with_payment_methods_by_period(start_date, end_date, limit=100, offset=0):
    """
    Retorna vendas dentro de um período de datas específico com paginação.
    Usa uma única consulta otimizada com LEFT JOIN e GROUP_CONCAT.
    Retorna um dicionário com 'sales' e 'total_count'.
    """
    conn = get_db_connection()

    # Adiciona o horário para pegar o dia inteiro
    start_datetime = f'{start_date} 00:00:00'
    end_datetime = f'{end_date} 23:59:59'

    # Consulta para contar o total de vendas
    count_query = '''
        SELECT COUNT(*) as total_count
        FROM sales s
        WHERE s.sale_date BETWEEN ? AND ? AND s.training_mode = 0
    '''
    count_row = conn.execute(count_query, (start_datetime, end_datetime)).fetchone()
    total_count = count_row['total_count']

    # Consulta para buscar vendas com paginação
    query = '''
        SELECT
            s.id, s.sale_date, s.total_amount, s.user_id, s.cash_session_id, s.training_mode,
            s.session_sale_id, s.customer_name,
            u.username,
            GROUP_CONCAT(pm.name, ', ') as payment_methods_str
        FROM sales s
        LEFT JOIN sale_payments sp ON s.id = sp.sale_id
        LEFT JOIN payment_methods pm ON sp.payment_method = pm.id
        LEFT JOIN users u ON s.user_id = u.id
        WHERE s.sale_date BETWEEN ? AND ? AND s.training_mode = 0
        GROUP BY s.id
        ORDER BY s.sale_date DESC
        LIMIT ? OFFSET ?
    '''

    rows = conn.execute(query, (start_datetime, end_datetime, limit, offset)).fetchall()
    conn.close()

    sales = []
    for row in rows:
        sale = dict(row)
        # Usa a função from_cents que já existe no seu utils.py
        sale['total_amount'] = to_reais(sale['total_amount'])
        sales.append(sale)

    return {'sales': sales, 'total_count': total_count}

def get_items_for_sale(sale_id):
    conn = get_db_connection()
    rows = conn.execute('''
        SELECT p.description, si.quantity, si.unit_price, si.total_price, p.sale_type
        FROM sale_items si
        JOIN products p ON si.product_id = p.id
        WHERE si.sale_id = ?
    ''', (sale_id,)).fetchall()
    conn.close()
    items = []
    for row in rows:
        item = dict(row)
        if item['unit_price'] is not None:
            item['unit_price'] = to_reais(item['unit_price'])
        if item['total_price'] is not None:
            item['total_price'] = to_reais(item['total_price'])
        items.append(item)
    return items

def get_next_session_sale_id(cash_session_id: int) -> int:
    """Calcula o próximo ID de venda para a sessão de caixa atual."""
    if not cash_session_id:
        return None
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT MAX(session_sale_id) FROM sales WHERE cash_session_id = ?",
        (cash_session_id,)
    )
    max_id = cursor.fetchone()[0]
    conn.close()
    return (max_id or 0) + 1

def register_sale_with_user(total_amount, payments, items, change_amount, user_id=None, cash_session_id=None, training_mode=False, customer_name: Optional[str] = None, discount_value=0.0, cursor=None):
    """Registra venda com informações de usuário, sessão, e cliente. Suporta transações externas via cursor."""
    manage_transaction = cursor is None
    conn = None
    
    if manage_transaction:
        conn = get_db_connection()
        cursor = conn.cursor()

    try:
        # Garante que os valores finais sejam inteiros
        total_amount_cents = int(to_cents(total_amount))
        change_amount_cents = int(to_cents(change_amount))
        
        # Validação dos IDs
        if user_id is not None:
            logging.debug(f"Validating user_id: {user_id}")
            cursor.execute("SELECT id FROM users WHERE id = ?", (user_id,))
            if cursor.fetchone() is None:
                logging.warning(f"User ID {user_id} not found. Setting to NULL.")
                user_id = None
            logging.debug("user_id is valid")
        
        if cash_session_id is not None:
            logging.debug(f"Validating cash_session_id: {cash_session_id}")
            cursor.execute("SELECT id FROM cash_sessions WHERE id = ?", (cash_session_id,))
            if cursor.fetchone() is None:
                logging.warning(f"Cash session ID {cash_session_id} not found. Setting to NULL.")
                cash_session_id = None
            logging.debug("cash_session_id is valid")

        # Nova lógica para o ID da sessão
        # Precisamos recalcular aqui se estamos numa transação? Sim, pois o cursor tem o contexto.
        # Porém, get_next_session_sale_id abre sua própria conexão. 
        # Idealmente deveríamos passar o cursor para get_next_session_sale_id também, 
        # mas por hora, vamos manter simples pois é apenas leitura antes do insert.
        # Mas espere, se estamos numa transação e acabamos de inserir uma venda na sessão, 
        # a leitura isolada pode não ver. 
        # Vamos fazer a query diretamente aqui usando o cursor atual para garantir consistência.
        
        cursor.execute("SELECT MAX(session_sale_id) FROM sales WHERE cash_session_id = ?", (cash_session_id,))
        max_id_row = cursor.fetchone()
        max_id = max_id_row[0] if max_id_row else 0
        session_sale_id = (max_id or 0) + 1
        
        logging.debug(f"Next session_sale_id: {session_sale_id}")

        # Corrige problema de timezone: usa horário local ao invés de UTC
        from datetime import datetime
        sale_date_local = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        logging.debug(f"Executing INSERT INTO sales with user_id: {user_id}, cash_session_id: {cash_session_id}, sale_date: {sale_date_local}")
        cursor.execute('''
            INSERT INTO sales (sale_date, total_amount, user_id, cash_session_id, training_mode, change_amount, session_sale_id, customer_name, discount_value)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (sale_date_local, total_amount_cents, user_id, cash_session_id, training_mode, change_amount_cents, session_sale_id, customer_name, discount_value))
        logging.debug("Finished INSERT INTO sales")

        sale_id = cursor.lastrowid
        logging.debug(f"Sale registered with sale_id: {sale_id}")

        for item in items:
            # Garante que os valores de preço também sejam inteiros
            unit_price_cents = int(to_cents(item['unit_price']))
            total_price_cents = int(to_cents(item['total_price']))
            quantity_float = float(item['quantity']) # Correção anterior mantida
            peso_kg = float(item.get('peso_kg', 0.0)) # Pega o peso ou default para 0.0

            # Valida o ID do produto
            logging.debug(f"Validating product with id {item['id']}")
            cursor.execute("SELECT id FROM products WHERE id = ?", (item['id'],))
            if cursor.fetchone() is None:
                raise sqlite3.Error(f"Produto com ID {item['id']} não encontrado.")
            logging.debug(f"Product with id {item['id']} is valid")

            logging.debug(f"Inserting sale_item with sale_id: {sale_id}, product_id: {item['id']}")
            insert_values = (sale_id, item['id'], quantity_float, unit_price_cents, total_price_cents, peso_kg)
            logging.debug(f"Values for sale_items: {insert_values}")
            cursor.execute('''
                INSERT INTO sale_items (sale_id, product_id, quantity, unit_price, total_price, peso_kg)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', insert_values)
            logging.debug("Finished INSERT INTO sale_items")

            # Só atualiza estoque se não for modo treinamento e o item for vendido por unidade.
            if not training_mode and item.get('sale_type') == 'unit':
                # Verifica se há estoque suficiente
                logging.debug(f"Checking stock for product_id {item['id']}")
                stock_check = cursor.execute('SELECT stock FROM products WHERE id = ?', (item['id'],)).fetchone()
                # Nota: Em uma transação, isso vê as alterações pendentes da própria transação? 
                # Sim, na mesma conexão vê.
                
                if stock_check and stock_check[0] < item['quantity']:
                    raise sqlite3.Error(f"Estoque insuficiente para o produto: {item['description']}")
                logging.debug("Stock is sufficient")

                logging.debug(f"Executing UPDATE products for product_id {item['id']}")
                cursor.execute("UPDATE products SET stock = stock - ?, sync_status = CASE WHEN sync_status = 'pending_create' THEN 'pending_create' ELSE 'pending_update' END WHERE id = ?", (float(item['quantity']), item['id']))
                logging.debug("Finished UPDATE products")

        # Se já for uma lista (novo formato), usa diretamente
        payments_list = payments

        # Insere os pagamentos individuais na tabela sale_payments
        for payment in payments_list:
            payment_amount_cents = int(to_cents(payment['amount']))
            cursor.execute('''
                INSERT INTO sale_payments (sale_id, payment_method, amount)
                VALUES (?, ?, ?)
            ''', (sale_id, payment['method'], payment_amount_cents))

        if manage_transaction:
            logging.debug("Committing transaction")
            conn.commit()
            logging.debug("Transaction committed")

        if user_id:
            # Audit log geralmente usa sua própria conexão em log_audit, 
            # não vamos misturar para não complicar, a menos que seja crítico.
            # Se a transação falhar depois, o log existirá mas a venda não.
            # Para auditoria perfeita, log_audit tambem deveria aceitar cursor,
            # mas vamos aceitar esse pequeno risco por enquanto para simplificar.
            try:
                log_audit(user_id, 'SALE', 'sales', sale_id)
            except Exception as e:
                logging.warning(f"Failed to log audit for sale {sale_id}: {e}")

        # Retorna um dicionário com os dados da venda para a notificação
        sale_data = {
            "id": sale_id,
            "session_sale_id": session_sale_id,
            "customer_name": customer_name,
            "total_amount": total_amount,
            "payments": payments,
            "items": items,
            "change_amount": change_amount,
            "discount_value": discount_value
        }
        return True, sale_data
    except sqlite3.Error as e:
        if manage_transaction and conn:
            conn.rollback()
        # Se gerenciado externamente, a exceção sobe e quem chamou faz rollback
        if not manage_transaction:
            raise e
        return False, {"error": f"Erro ao registrar a venda: {e}"}
    finally:
        if manage_transaction and conn:
            conn.close()
