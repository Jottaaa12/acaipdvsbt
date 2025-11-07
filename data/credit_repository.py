import sqlite3
import logging
from decimal import Decimal
from .connection import get_db_connection
from .audit_repository import log_audit
from utils import to_cents, to_reais

def add_customer(name, cpf=None, phone=None, address=None, credit_limit=0, is_blocked=0, cursor=None):
    """Adiciona um novo cliente."""
    manage_connection = cursor is None
    conn = None
    if manage_connection:
        conn = get_db_connection()
        cursor = conn.cursor()
    try:
        credit_limit_cents = to_cents(Decimal(str(credit_limit)))
        cursor.execute('''
            INSERT INTO customers (name, cpf, phone, address, credit_limit, is_blocked)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (name, cpf, phone, address, credit_limit_cents, is_blocked))
        customer_id = cursor.lastrowid
        if manage_connection:
            conn.commit()
        return True, customer_id
    except sqlite3.IntegrityError as e:
        if manage_connection:
            conn.rollback()
        return False, f"Erro: Cliente com este CPF ou combinação de nome/telefone já existe. {e}"
    except sqlite3.Error as e:
        if manage_connection:
            conn.rollback()
        return False, f"Erro de banco de dados: {e}"
    finally:
        if manage_connection and conn:
            conn.close()

def create_credit_sale(customer_id, amount, user_id, sale_id=None, observations=None, due_date=None, cursor=None):
    """Cria um novo registro de venda a crédito (fiado)."""
    manage_connection = cursor is None
    conn = None
    if manage_connection:
        conn = get_db_connection()
        cursor = conn.cursor()

    try:
        # Validate foreign keys
        cursor.execute("SELECT id FROM users WHERE id = ?", (user_id,))
        if cursor.fetchone() is None:
            raise sqlite3.IntegrityError(f"User with ID {user_id} not found.")

        cursor.execute("SELECT id FROM customers WHERE id = ?", (customer_id,))
        if cursor.fetchone() is None:
            raise sqlite3.IntegrityError(f"Customer with ID {customer_id} not found.")
            
        amount_cents = to_cents(Decimal(str(amount)))
        cursor.execute('''
            INSERT INTO credit_sales (customer_id, sale_id, amount, observations, due_date, user_id)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (customer_id, sale_id, amount_cents, observations, due_date, user_id))
        credit_sale_id = cursor.lastrowid
        
        if manage_connection:
            conn.commit()
        
        # O log de auditoria deve ser tratado pela função que gerencia a transação
        # log_audit(user_id, 'CREATE_CREDIT_SALE', 'credit_sales', credit_sale_id, new_values=f"Cliente: {customer_id}, Valor: {amount}")
        
        return True, credit_sale_id
    except sqlite3.Error:
        if manage_connection and conn:
            conn.rollback()
        # Re-raise the exception to be handled by the caller
        raise
    finally:
        if manage_connection and conn:
            conn.close()

def associate_sale_to_credit(credit_sale_id, sale_id, cursor=None):
    """Associa o ID de uma venda a um registro de fiado existente."""
    manage_connection = cursor is None
    conn = None
    if manage_connection:
        conn = get_db_connection()
        cursor = conn.cursor()
    try:
        cursor.execute("UPDATE credit_sales SET sale_id = ?, sync_status = CASE WHEN sync_status = 'pending_create' THEN 'pending_create' ELSE 'pending_update' END WHERE id = ?", (sale_id, credit_sale_id))
        if manage_connection:
            conn.commit()
        logging.info(f"Venda ID {sale_id} associada com sucesso ao fiado ID {credit_sale_id}.")
        return True
    except sqlite3.Error as e:
        if manage_connection and conn:
            conn.rollback()
        logging.error(f"Erro de banco de dados ao associar venda ao fiado: {e}")
        raise
    finally:
        if manage_connection and conn:
            conn.close()

# As funções abaixo não precisam de gerenciamento de transação explícito pois são apenas de leitura.
# ... (o resto do arquivo permanece o mesmo)
def get_all_customers():
    """Retorna todos os clientes não deletados."""
    conn = get_db_connection()
    rows = conn.execute('SELECT * FROM customers WHERE is_deleted = 0 ORDER BY name').fetchall()
    conn.close()
    customers = []
    for row in rows:
        customer = dict(row)
        customer['credit_limit'] = to_reais(customer['credit_limit'])
        customers.append(customer)
    return customers

def update_customer(customer_id, name, cpf=None, phone=None, address=None, credit_limit=0, is_blocked=0):
    """Atualiza os dados de um cliente."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        credit_limit_cents = to_cents(Decimal(str(credit_limit)))
        cursor.execute('''
            UPDATE customers
            SET name = ?, cpf = ?, phone = ?, address = ?, credit_limit = ?, is_blocked = ?,
                sync_status = CASE WHEN sync_status = 'pending_create' THEN 'pending_create' ELSE 'pending_update' END
            WHERE id = ?
        ''', (name, cpf, phone, address, credit_limit_cents, is_blocked, customer_id))
        conn.commit()
        return True, "Cliente atualizado com sucesso."
    except sqlite3.IntegrityError as e:
        return False, f"Erro: Cliente com este CPF ou combinação de nome/telefone já existe. {e}"
    except sqlite3.Error as e:
        return False, f"Erro de banco de dados: {e}"
    finally:
        conn.close()

def delete_customer(customer_id):
    """Marca um cliente como deletado (soft delete)."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Verifica se o cliente tem saldo devedor antes de "excluir"
        balance = get_customer_balance(customer_id)
        if balance > Decimal('0.00'):
            return False, "Este cliente não pode ser excluído pois possui saldo devedor."

        cursor.execute("""UPDATE customers SET is_deleted = 1, sync_status = 'pending_update' WHERE id = ?""", (customer_id,))
        conn.commit()
        if cursor.rowcount > 0:
            return True, "Cliente marcado como deletado com sucesso."
        return False, "Cliente não encontrado."
    except sqlite3.Error as e:
        return False, f"Erro de banco de dados: {e}"
    finally:
        conn.close()

def search_customers(search_term):
    """Busca clientes não deletados por nome, CPF ou telefone."""
    conn = get_db_connection()
    search_query = f'%{search_term}%'
    rows = conn.execute('''
        SELECT * FROM customers
        WHERE (name LIKE ? OR cpf LIKE ? OR phone LIKE ?) AND is_deleted = 0
        ORDER BY name
        LIMIT 20
    ''', (search_query, search_query, search_query)).fetchall()
    conn.close()
    customers = []
    for row in rows:
        customer = dict(row)
        customer['credit_limit'] = to_reais(customer['credit_limit'])
        customers.append(customer)
    return customers

def get_credit_sale_details(credit_sale_id):
    """Busca detalhes de uma venda a crédito, incluindo pagamentos."""
    conn = get_db_connection()
    sale_row = conn.execute('''
        SELECT cs.*, c.name as customer_name, u.username
        FROM credit_sales cs
        JOIN customers c ON cs.customer_id = c.id
        JOIN users u ON cs.user_id = u.id
        WHERE cs.id = ? AND c.is_deleted = 0 AND u.is_deleted = 0
    ''', (credit_sale_id,)).fetchone()

    if not sale_row:
        conn.close()
        return None

    payments_rows = conn.execute('''
        SELECT * FROM credit_payments WHERE credit_sale_id = ? ORDER BY payment_date
    ''', (credit_sale_id,)).fetchall()
    conn.close()

    sale_details = dict(sale_row)
    sale_details['amount'] = to_reais(sale_details['amount'])

    payments = []
    total_paid = Decimal('0.00')
    for row in payments_rows:
        payment = dict(row)
        amount_paid = to_reais(payment['amount_paid'])
        payment['amount_paid'] = amount_paid
        total_paid += amount_paid
        payments.append(payment)

    sale_details['payments'] = payments
    sale_details['total_paid'] = total_paid
    sale_details['balance_due'] = sale_details['amount'] - total_paid

    return sale_details

def get_credit_sales_by_period(start_date, end_date):
    """Busca todas as vendas a crédito (fiados) criadas em um período específico."""
    conn = get_db_connection()
    query = """
        SELECT cs.id, cs.amount, cs.status, cs.created_date, c.name as customer_name
        FROM credit_sales cs
        JOIN customers c ON cs.customer_id = c.id
        WHERE DATE(cs.created_date) BETWEEN ? AND ? AND c.is_deleted = 0 AND cs.is_deleted = 0
        ORDER BY cs.created_date DESC
    """
    rows = conn.execute(query, (start_date, end_date)).fetchall()
    conn.close()

    sales = []
    for row in rows:
        sale = dict(row)
        sale['amount'] = to_reais(sale['amount'])
        sales.append(sale)
    return sales

def get_credit_payments_by_period(start_date, end_date):
    """Busca todos os pagamentos de fiados recebidos em um período específico."""
    conn = get_db_connection()
    query = """
        SELECT p.payment_method, SUM(p.amount_paid) as total_paid
        FROM credit_payments p
        JOIN credit_sales cs ON p.credit_sale_id = cs.id
        WHERE DATE(p.payment_date) BETWEEN ? AND ?
        GROUP BY p.payment_method
    """
    rows = conn.execute(query, (start_date, end_date)).fetchall()
    conn.close()

    payments = []
    for row in rows:
        payment = dict(row)
        payment['total_paid'] = to_reais(payment['total_paid'])
        payments.append(payment)
    return payments

def get_all_pending_credit_sales():
    """Busca todos os fiados com status 'pending' ou 'partially_paid'."""
    conn = get_db_connection()
    query = """
        SELECT cs.id, cs.amount, cs.status, cs.created_date, c.name as customer_name,
               (SELECT COALESCE(SUM(amount_paid), 0) FROM credit_payments WHERE credit_sale_id = cs.id) as total_paid_cents
        FROM credit_sales cs
        JOIN customers c ON cs.customer_id = c.id
        WHERE cs.status IN ('pending', 'partially_paid') AND c.is_deleted = 0 AND cs.is_deleted = 0
        ORDER BY cs.created_date DESC
    """
    rows = conn.execute(query).fetchall()
    conn.close()

    sales = []
    for row in rows:
        sale = dict(row)
        total_amount = to_reais(sale['amount'])
        total_paid = to_reais(sale['total_paid_cents'])
        sale['amount'] = total_amount
        sale['total_paid'] = total_paid
        sale['balance_due'] = total_amount - total_paid
        sales.append(sale)
    return sales

def get_credit_sales(status_filter=None):
    """Busca todas as vendas a crédito, com opção de filtro por status."""
    conn = get_db_connection()
    
    query = '''
        SELECT 
            cs.id, cs.amount, cs.status, cs.created_date, cs.due_date,
            c.name as customer_name,
            u.username as user_name,
            (SELECT COALESCE(SUM(amount_paid), 0) FROM credit_payments WHERE credit_sale_id = cs.id) as total_paid_cents
        FROM credit_sales cs
        JOIN customers c ON cs.customer_id = c.id
        JOIN users u ON cs.user_id = u.id
        WHERE c.is_deleted = 0 AND u.is_deleted = 0 AND cs.is_deleted = 0
    '''
    params = []
    if status_filter and status_filter != 'all':
        query += " AND cs.status = ?"
        params.append(status_filter)

    query += " ORDER BY cs.created_date DESC"

    rows = conn.execute(query, params).fetchall()
    conn.close()

    sales = []
    for row in rows:
        sale = dict(row)
        total_amount = to_reais(sale['amount'])
        total_paid = to_reais(sale['total_paid_cents'])
        sale['amount'] = total_amount
        sale['total_paid'] = total_paid
        sale['balance_due'] = total_amount - total_paid
        sales.append(sale)
    return sales

def get_customer_balance(customer_id):
    """Calcula o saldo devedor total de um cliente."""
    conn = get_db_connection()
    cursor = conn.cursor()
    # Calcula o total devido somando o valor das vendas a prazo pendentes
    # e subtraindo os pagamentos já realizados.
    cursor.execute("""
        SELECT
            (SELECT COALESCE(SUM(cs.amount), 0) FROM credit_sales cs WHERE cs.customer_id = ? AND cs.status != 'cancelled' AND cs.is_deleted = 0) -
            (SELECT COALESCE(SUM(cp.amount_paid), 0) FROM credit_payments cp JOIN credit_sales cs ON cp.credit_sale_id = cs.id WHERE cs.customer_id = ? AND cp.is_deleted = 0)
    """, (customer_id, customer_id))
    balance_cents = cursor.fetchone()[0]
    conn.close()
    return to_reais(balance_cents if balance_cents else 0)

def get_customer_by_id(customer_id):
    """Busca um cliente pelo seu ID."""
    conn = get_db_connection()
    row = conn.execute('SELECT * FROM customers WHERE id = ? AND is_deleted = 0', (customer_id,)).fetchone()
    conn.close()
    if not row:
        return None
    customer = dict(row)
    customer['credit_limit'] = to_reais(customer['credit_limit'])
    return customer

def get_credit_status_summary():
    """Calcula o número de contas a prazo vencidas e pendentes."""
    conn = get_db_connection()
    # Considera vencido se a data de vencimento passou e o status é pendente ou parcial
    overdue_count = conn.execute("""
        SELECT COUNT(id) FROM credit_sales
        WHERE status IN ('pending', 'partially_paid') AND due_date < DATE('now')
    """, ).fetchone()[0]
    
    # Total de contas pendentes (incluindo as vencidas)
    pending_count = conn.execute("""
        SELECT COUNT(id) FROM credit_sales
        WHERE status IN ('pending', 'partially_paid')
    """, ).fetchone()[0]
    
    conn.close()
    return {
        'overdue_count': overdue_count or 0,
        'pending_count': pending_count or 0
    }

def add_credit_payment(credit_sale_id, amount_paid, user_id, payment_method, cash_session_id=None):
    """Adiciona um pagamento a uma venda a crédito."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        amount_paid_cents = to_cents(Decimal(str(amount_paid)))
        cursor.execute('''
            INSERT INTO credit_payments (credit_sale_id, amount_paid, user_id, payment_method, cash_session_id)
            VALUES (?, ?, ?, ?, ?)
        ''', (credit_sale_id, amount_paid_cents, user_id, payment_method, cash_session_id))
        
        # Atualiza o status da venda a crédito
        cursor.execute('''
            UPDATE credit_sales
            SET status = CASE
                WHEN (SELECT SUM(amount_paid) FROM credit_payments WHERE credit_sale_id = ?) >= amount THEN 'paid'
                ELSE 'partially_paid'
            END,
            sync_status = CASE WHEN sync_status = 'pending_create' THEN 'pending_create' ELSE 'pending_update' END
            WHERE id = ?
        ''', (credit_sale_id, credit_sale_id))
        
        conn.commit()
        log_audit(user_id, 'ADD_CREDIT_PAYMENT', 'credit_payments', cursor.lastrowid, new_values=f"Valor: {amount_paid}")
        return True, "Pagamento registrado com sucesso."
    except sqlite3.Error as e:
        conn.rollback()
        return False, f"Erro de banco de dados: {e}"
    finally:
        conn.close()

def update_credit_sale_status(credit_sale_id, new_status, user_id):
    """Atualiza o status de uma venda a crédito (ex: para 'cancelled')."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    valid_statuses = ['pending', 'partially_paid', 'paid', 'cancelled']
    if new_status not in valid_statuses:
        return False, f"Status '{new_status}' inválido."

    try:
        cursor.execute(
            'UPDATE credit_sales SET status = ?, sync_status = CASE WHEN sync_status = \'pending_create\' THEN \'pending_create\' ELSE \'pending_update\' END WHERE id = ?',
            (new_status, credit_sale_id)
        )
        conn.commit()

        if cursor.rowcount > 0:
            log_audit(user_id, 'UPDATE_CREDIT_STATUS', 'credit_sales', credit_sale_id, new_values=f"Novo status: {new_status}")
            return True, "Status da venda a prazo atualizado com sucesso."
        else:
            return False, "Venda a prazo não encontrada."
            
    except sqlite3.Error as e:
        conn.rollback()
        return False, f"Erro de banco de dados: {e}"
    finally:
        conn.close()

def get_customer_by_phone(phone):
    """Busca um cliente pelo seu número de telefone (correspondência exata)."""
    if not phone:
        return None
    conn = get_db_connection()
    row = conn.execute('SELECT * FROM customers WHERE phone = ? AND is_deleted = 0', (phone,)).fetchone()
    conn.close()
    if not row:
        return None
    customer = dict(row)
    customer['credit_limit'] = to_reais(customer['credit_limit'])
    return customer

