import sqlite3
import logging
from decimal import Decimal
from datetime import datetime
from .connection import get_db_connection
from .audit_repository import log_audit
from utils import to_cents, to_reais

def open_cash_session(user_id, initial_amount):
    """Abre nova sessão de caixa."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Verifica se já existe caixa aberto
    existing = cursor.execute('''
        SELECT id FROM cash_sessions 
        WHERE status = 'open'
    ''').fetchone()
    
    if existing:
        conn.close()
        return None, "Já existe um caixa aberto"
    
    initial_amount_decimal = Decimal(str(initial_amount)).quantize(Decimal('0.01'))
    initial_amount_cents = to_cents(initial_amount_decimal)
    cursor.execute('''
        INSERT INTO cash_sessions (user_id, initial_amount) 
        VALUES (?, ?)
    ''', (user_id, initial_amount_cents))
    
    session_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    log_audit(user_id, 'OPEN_CASH', 'cash_sessions', session_id)
    return session_id, "Caixa aberto com sucesso"

def _parse_datetime(dt_string):
    if not dt_string:
        return None
    for fmt in ('%Y-%m-%d %H:%M:%S.%f', '%Y-%m-%d %H:%M:%S'):
        try:
            return datetime.strptime(dt_string, fmt)
        except ValueError:
            pass
    return None

def get_current_cash_session():
    """Retorna a sessão de caixa atual (aberta)."""
    conn = get_db_connection()
    row = conn.execute('''
        SELECT cs.*, u.username 
        FROM cash_sessions cs
        JOIN users u ON cs.user_id = u.id
        WHERE cs.status = 'open'
    ''').fetchone()
    conn.close()
    if row:
        session = dict(row)
        session['open_time'] = _parse_datetime(session['open_time'])
        for field in ['initial_amount', 'final_amount', 'expected_amount', 'difference']:
            if session.get(field) is not None:
                session[field] = to_reais(session[field])
        return session
    return None

def add_cash_movement(session_id, user_id, movement_type, amount, reason, authorized_by_id=None):
    """Adiciona movimento de caixa (suprimento/sangria) com autorização opcional."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    amount_decimal = Decimal(str(amount)).quantize(Decimal('0.01'))
    amount_cents = to_cents(amount_decimal)
    cursor.execute('''
        INSERT INTO cash_movements (session_id, user_id, type, amount, reason, authorized_by_id)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (session_id, user_id, movement_type, amount_cents, reason, authorized_by_id))
    
    movement_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    log_audit(user_id, f'CASH_{movement_type.upper()}', 'cash_movements', movement_id, new_values=f"Autorizado por ID: {authorized_by_id}" if authorized_by_id else "")
    return movement_id

def close_cash_session(session_id, user_id, final_amount, cash_counts, observations=None):
    """Fecha sessão de caixa com contagem. Operação transacional."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # session_cents já vem com valores em centavos do DB
        session_cents = cursor.execute('SELECT * FROM cash_sessions WHERE id = ?', (session_id,)).fetchone()
        if not session_cents:
            return False, "Sessão não encontrada"

        # Soma dos pagamentos em dinheiro (valores já em centavos no DB)
        total_cash_payments_cents = cursor.execute('''
            SELECT COALESCE(SUM(sp.amount), 0) as total
            FROM sale_payments sp
            JOIN sales s ON sp.sale_id = s.id
            WHERE s.cash_session_id = ? AND sp.payment_method = 'Dinheiro' AND s.training_mode = 0
        ''', (session_id,)).fetchone()['total']

        # Soma do troco (valores já em centavos no DB)
        total_change_cents = cursor.execute('''
            SELECT COALESCE(SUM(s.change_amount), 0) as total
            FROM sales s
            WHERE s.cash_session_id = ? AND s.training_mode = 0
        ''', (session_id,)).fetchone()['total']

        cash_sales_cents = total_cash_payments_cents - total_change_cents

        # Soma movimentos (valores já em centavos no DB)
        movements_cents = cursor.execute('''
            SELECT 
                COALESCE(SUM(CASE WHEN type = 'suprimento' THEN amount ELSE 0 END), 0) as suprimentos,
                COALESCE(SUM(CASE WHEN type = 'sangria' THEN amount ELSE 0 END), 0) as sangrias
            FROM cash_movements 
            WHERE session_id = ?
        ''', (session_id,)).fetchone()

        final_amount_decimal = Decimal(str(final_amount)).quantize(Decimal('0.01'))
        final_amount_cents = to_cents(final_amount_decimal)
        
        expected_amount_cents = session_cents['initial_amount'] + cash_sales_cents + movements_cents['suprimentos'] - movements_cents['sangrias']
        difference_cents = final_amount_cents - expected_amount_cents

        # Atualiza sessão com valores em centavos
        cursor.execute('''
            UPDATE cash_sessions 
            SET close_time = CURRENT_TIMESTAMP, final_amount = ?, expected_amount = ?, 
                difference = ?, status = 'closed', observations = ?
            WHERE id = ?
        ''', (final_amount_cents, expected_amount_cents, difference_cents, observations, session_id))

        # Salva contagem
        for denomination, total_counted_for_denom in cash_counts.items():
            if total_counted_for_denom > 0:
                value_per_unit = get_denomination_value(denomination)
                # A 'quantity' aqui é uma estimativa, o mais importante é o valor total
                quantity_estimate = (total_counted_for_denom * 100) / value_per_unit if value_per_unit > 0 else 0
                total_value_cents = to_cents(Decimal(str(total_counted_for_denom)))

                cursor.execute('''
                    INSERT INTO cash_counts (session_id, denomination, quantity, total_value)
                    VALUES (?, ?, ?, ?)
                ''', (session_id, denomination, int(quantity_estimate), total_value_cents))

        conn.commit()

        # Log de auditoria
        log_audit(user_id, 'CLOSE_CASH', 'cash_sessions', session_id, new_values=f"Observações: {observations}")

        return True, {
            'expected': to_reais(expected_amount_cents),
            'counted': to_reais(final_amount_cents),
            'difference': to_reais(difference_cents)
        }
    except sqlite3.Error as e:
        logging.error(f"Erro ao fechar o caixa: {e}", exc_info=True)
        conn.rollback()
        return False, f"Erro de banco de dados ao fechar o caixa: {e}"
    finally:
        if conn:
            conn.close()

def get_denomination_value(denomination):
    """Retorna valor da denominação em CENTAVOS."""
    values = {
        '200': 20000, '100': 10000, '50': 5000, '20': 2000, '10': 1000,
        '5': 500, '2': 200, '1': 100, '0.50': 50, '0.25': 25,
        '0.10': 10, '0.05': 5, '0.01': 1
    }
    return values.get(denomination, 0)

def get_cash_session_report(session_id):
    """Gera relatório completo da sessão de caixa."""
    conn = get_db_connection()
    
    # Dados da sessão
    session_row = conn.execute('''
        SELECT cs.*, u.username 
        FROM cash_sessions cs
        JOIN users u ON cs.user_id = u.id
        WHERE cs.id = ?
    ''', (session_id,)).fetchone()
    
    session_dict = None
    if session_row:
        session_dict = dict(session_row)
        session_dict['open_time'] = _parse_datetime(session_dict['open_time'])
        session_dict['close_time'] = _parse_datetime(session_dict['close_time'])
        for field in ['initial_amount', 'final_amount', 'expected_amount', 'difference']:
            if session_dict.get(field) is not None:
                session_dict[field] = to_reais(session_dict[field])
        if 'observations' not in session_dict or session_dict['observations'] is None:
            session_dict['observations'] = ''

    # Vendas
    total_change_cents = conn.execute('''
        SELECT COALESCE(SUM(change_amount), 0) as total
        FROM sales
        WHERE cash_session_id = ? AND training_mode = 0
    ''', (session_id,)).fetchone()['total']

    sales_rows = conn.execute('''
        SELECT
            sp.payment_method,
            COUNT(DISTINCT s.id) as count,
            SUM(sp.amount) as total
        FROM sale_payments sp
        JOIN sales s ON sp.sale_id = s.id
        WHERE s.cash_session_id = ? AND s.training_mode = 0
        GROUP BY sp.payment_method
    ''', (session_id,)).fetchall()
    sales_list = []
    for row in sales_rows:
        sale = dict(row)
        if sale['payment_method'] == 'Dinheiro':
            sale['total'] -= total_change_cents
        
        if sale.get('total') is not None:
            sale['total'] = to_reais(sale['total'])
        sales_list.append(sale)

    # Movimentos
    movements_rows = conn.execute('''
        SELECT cm.*, u_auth.username as authorized_by
        FROM cash_movements cm
        LEFT JOIN users u_auth ON cm.authorized_by_id = u_auth.id
        WHERE cm.session_id = ?
        ORDER BY cm.timestamp
    ''', (session_id,)).fetchall()
    movements_list = []
    for row in movements_rows:
        movement = dict(row)
        movement['timestamp'] = _parse_datetime(movement['timestamp'])
        if movement.get('amount') is not None:
            movement['amount'] = to_reais(movement['amount'])
        movements_list.append(movement)

    # Contagem
    counts_rows = conn.execute('''
        SELECT * FROM cash_counts 
        WHERE session_id = ?
        ORDER BY denomination DESC
    ''', (session_id,)).fetchall()
    counts_list = []
    for row in counts_rows:
        count = dict(row)
        if count.get('total_value') is not None:
            count['total_value'] = to_reais(count['total_value'])
        counts_list.append(count)

    conn.close()    
    total_revenue = sum(item['total'] for item in sales_list)
    total_sangria = sum(m['amount'] for m in movements_list if m['type'] == 'sangria')
    total_weight_kg = get_total_weight_by_cash_session(session_id)

    return {
        'session': session_dict,
        'sales': sales_list,
        'movements': movements_list,
        'counts': counts_list,
        'total_revenue': total_revenue,
        'total_after_sangria': total_revenue - total_sangria,
        'total_weight_kg': total_weight_kg
    }

def get_sales_by_cash_session(session_id):
    """Retorna todas as vendas de uma sessão de caixa."""
    conn = get_db_connection()
    sales = conn.execute('''
        SELECT * FROM sales 
        WHERE cash_session_id = ? AND training_mode = 0
        ORDER BY sale_date
    ''', (session_id,)).fetchall()
    conn.close()
    return [dict(sale) for sale in sales]

def get_payment_summary_by_cash_session(session_id):
    """Retorna resumo de vendas por forma de pagamento para uma sessão."""
    conn = get_db_connection()

    total_change_cents = conn.execute('''
        SELECT COALESCE(SUM(change_amount), 0) as total
        FROM sales
        WHERE cash_session_id = ? AND training_mode = 0
    ''', (session_id,)).fetchone()['total']

    rows = conn.execute('''
        SELECT sp.payment_method, COUNT(DISTINCT sp.sale_id) as count, SUM(sp.amount) as total
        FROM sale_payments sp
        JOIN sales s ON sp.sale_id = s.id
        WHERE s.cash_session_id = ? AND s.training_mode = 0
        GROUP BY sp.payment_method
        ORDER BY sp.payment_method
    ''', (session_id,)).fetchall()
    conn.close()

    summary = []
    for row in rows:
        item = dict(row)
        if item['payment_method'] == 'Dinheiro':
            item['total'] -= total_change_cents
        
        if item.get('total') is not None:
            item['total'] = to_reais(item['total'])
        summary.append(item)
    return summary

def get_sales_summary_by_session(cash_session_id: int):
    """Retorna um resumo das vendas para uma sessão de caixa específica."""
    if not cash_session_id:
        return (0, Decimal('0.00'))
        
    conn = get_db_connection()
    cursor = conn.cursor()

    query = """
        SELECT
            COUNT(id),
            COALESCE(SUM(total_amount), 0)
        FROM sales 
        WHERE cash_session_id = ? AND training_mode = 0
    """
    
    cursor.execute(query, (cash_session_id,))
    result = cursor.fetchone()
    conn.close()

    num_sales = result[0] or 0
    total_revenue_cents = result[1] or 0
    
    return (num_sales, to_reais(total_revenue_cents))

def get_total_weight_by_cash_session(session_id: int) -> float:
    """Calcula a soma total de peso_kg para uma sessão de caixa."""
    if not session_id:
        return 0.0
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT SUM(si.peso_kg)
        FROM sale_items si
        JOIN sales s ON si.sale_id = s.id
        WHERE s.cash_session_id = ?
    """, (session_id,))
    total_weight = cursor.fetchone()[0]
    conn.close()
    return total_weight or 0.0

def get_cash_session_history(start_date, end_date, operator_id=None):
    """Busca o histórico de sessões de caixa fechadas em um período."""
    conn = get_db_connection()
    
    query = '''
        SELECT cs.id, u.username, cs.close_time, cs.difference
        FROM cash_sessions cs
        LEFT JOIN users u ON cs.user_id = u.id
        WHERE cs.status = 'closed'
        AND cs.close_time BETWEEN ? AND ?
    '''
    
    start_datetime = f'{start_date} 00:00:00'
    end_datetime = f'{end_date} 23:59:59'
    params = [start_datetime, end_datetime]
    
    if operator_id:
        query += ' AND cs.user_id = ?'
        params.append(operator_id)
        
    query += ' ORDER BY cs.close_time DESC'
    
    rows = conn.execute(query, params).fetchall()
    conn.close()
    
    history = []
    for row in rows:
        session = dict(row)
        session['difference'] = to_reais(session['difference'])
        session['close_time'] = _parse_datetime(session['close_time'])
        history.append(session)
        
    return history

def get_current_cash_status():
    """
    Calcula e retorna o status detalhado da sessão de caixa atual, se houver uma aberta.
    """
    session = get_current_cash_session()
    if not session:
        return {'status': 'FECHADO'}

    conn = get_db_connection()
    session_id = session['id']

    # Soma dos pagamentos em dinheiro (valores já em centavos no DB)
    total_cash_payments_cents = conn.execute('''
        SELECT COALESCE(SUM(sp.amount), 0) as total
        FROM sale_payments sp
        JOIN sales s ON sp.sale_id = s.id
        WHERE s.cash_session_id = ? AND sp.payment_method = 'Dinheiro' AND s.training_mode = 0
    ''', (session_id,)).fetchone()['total']

    # Soma do troco (valores já em centavos no DB)
    total_change_cents = conn.execute('''
        SELECT COALESCE(SUM(s.change_amount), 0) as total
        FROM sales s
        WHERE s.cash_session_id = ? AND s.training_mode = 0
    ''', (session_id,)).fetchone()['total']

    cash_sales_cents = total_cash_payments_cents - total_change_cents

    # Soma movimentos (valores já em centavos no DB)
    movements_cents = conn.execute('''
        SELECT 
            COALESCE(SUM(CASE WHEN type = 'suprimento' THEN amount ELSE 0 END), 0) as suprimentos,
            COALESCE(SUM(CASE WHEN type = 'sangria' THEN amount ELSE 0 END), 0) as sangrias
        FROM cash_movements 
        WHERE session_id = ?
    ''', (session_id,)).fetchone()
    
    conn.close()

    initial_amount_cents = to_cents(Decimal(str(session['initial_amount'])))
    current_balance_cents = initial_amount_cents + cash_sales_cents + movements_cents['suprimentos'] - movements_cents['sangrias']

    return {
        'status': 'ABERTO',
        'open_time': session['open_time'],
        'username': session['username'],
        'initial_amount': session['initial_amount'],
        'suprimentos': to_reais(movements_cents['suprimentos']),
        'sangrias': to_reais(movements_cents['sangrias']),
        'cash_sales': to_reais(cash_sales_cents),
        'current_balance': to_reais(current_balance_cents)
    }
