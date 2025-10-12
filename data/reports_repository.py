from decimal import Decimal
from datetime import datetime, timedelta
from .connection import get_db_connection
from utils import to_reais

def get_daily_summary(date_str):
    """Calcula um resumo de KPIs para um dia específico."""
    conn = get_db_connection()
    start_datetime = f'{date_str} 00:00:00'
    end_datetime = f'{date_str} 23:59:59'
    params = (start_datetime, end_datetime)

    query = """
        SELECT
            COALESCE(SUM(total_amount), 0) as total_revenue_cents,
            COUNT(id) as total_sales_count
        FROM sales
        WHERE sale_date BETWEEN ? AND ? AND training_mode = 0
    """
    summary_row = conn.execute(query, params).fetchone()
    conn.close()

    total_revenue = to_reais(summary_row['total_revenue_cents'])
    total_sales_count = summary_row['total_sales_count']
    average_ticket = total_revenue / total_sales_count if total_sales_count > 0 else Decimal('0.00')

    return {
        'total_revenue': total_revenue,
        'total_sales_count': total_sales_count,
        'average_ticket': average_ticket.quantize(Decimal('0.01'))
    }

def get_sales_by_hour(date_str):
    """Retorna o total de vendas agrupado por hora para uma data específica."""
    conn = get_db_connection()
    query = """
        SELECT
            CAST(strftime('%H', sale_date) AS INTEGER) as hour,
            SUM(total_amount) as total_cents
        FROM sales
        WHERE DATE(sale_date) = ? AND training_mode = 0
        GROUP BY hour
        ORDER BY hour;
    """
    rows = conn.execute(query, (date_str,)).fetchall()
    conn.close()
    
    sales_by_hour = []
    for row in rows:
        sales_by_hour.append({
            'hour': row['hour'],
            'total': to_reais(row['total_cents'])
        })
    return sales_by_hour

def get_sales_by_product_group(start_date, end_date):
    """Retorna o faturamento total por grupo de produto em um período."""
    conn = get_db_connection()
    start_datetime = f'{start_date} 00:00:00'
    end_datetime = f'{end_date} 23:59:59'
    
    query = """
        SELECT
            pg.name as group_name,
            SUM(si.total_price) as total_cents
        FROM sale_items si
        JOIN sales s ON si.sale_id = s.id
        JOIN products p ON si.product_id = p.id
        JOIN product_groups pg ON p.group_id = pg.id
        WHERE s.sale_date BETWEEN ? AND ? AND s.training_mode = 0
        GROUP BY pg.name
        HAVING total_cents > 0
        ORDER BY total_cents DESC;
    """
    rows = conn.execute(query, (start_datetime, end_datetime)).fetchall()
    conn.close()
    
    sales_by_group = []
    for row in rows:
        sales_by_group.append({
            'group_name': row['group_name'],
            'total': to_reais(row['total_cents'])
        })
    return sales_by_group

def get_latest_sales(limit=5):
    """Busca as últimas 'N' vendas, incluindo o nome do usuário."""
    conn = get_db_connection()
    query = """
        SELECT
            s.id,
            s.sale_date,
            s.total_amount,
            u.username
        FROM sales s
        LEFT JOIN users u ON s.user_id = u.id
        WHERE s.training_mode = 0
        ORDER BY s.sale_date DESC
        LIMIT ?;
    """
    rows = conn.execute(query, (limit,)).fetchall()
    conn.close()
    
    latest_sales = []
    for row in rows:
        latest_sales.append({
            'id': row['id'],
            'sale_date': datetime.strptime(row['sale_date'], '%Y-%m-%d %H:%M:%S.%f' if '.' in row['sale_date'] else '%Y-%m-%d %H:%M:%S'),
            'total_amount': to_reais(row['total_amount']),
            'username': row['username'] if row['username'] else 'N/A'
        })
    return latest_sales

def get_sales_report(start_date, end_date):
    """Gera um relatório de vendas consolidado para um período."""
    conn = get_db_connection()

    start_datetime = f'{start_date} 00:00:00'
    end_datetime = f'{end_date} 23:59:59'
    params = (start_datetime, end_datetime)

    # 1. Resumo Geral
    general_summary_query = '''
        SELECT
            COALESCE(SUM(total_amount), 0) as total_revenue,
            COUNT(id) as total_sales_count
        FROM sales
        WHERE sale_date BETWEEN ? AND ? AND training_mode = 0
    '''
    general_summary_row = conn.execute(general_summary_query, params).fetchone()

    # 2. Vendas por Forma de Pagamento - Agora usando a tabela sale_payments
    total_change_cents = conn.execute('''
        SELECT COALESCE(SUM(change_amount), 0) as total
        FROM sales
        WHERE sale_date BETWEEN ? AND ? AND training_mode = 0
    ''', params).fetchone()['total']

    payment_method_query = '''
        SELECT
            sp.payment_method,
            COALESCE(SUM(sp.amount), 0) as total,
            COUNT(DISTINCT sp.sale_id) as count
        FROM sale_payments sp
        JOIN sales s ON sp.sale_id = s.id
        WHERE s.sale_date BETWEEN ? AND ? AND s.training_mode = 0
        GROUP BY sp.payment_method
        ORDER BY total DESC
    '''
    payment_methods_rows = conn.execute(payment_method_query, params).fetchall()

    # 3. Produtos Mais Vendidos
    top_products_query = '''
        SELECT
            p.description,
            SUM(si.quantity) as quantity_sold,
            SUM(si.total_price) as revenue
        FROM sale_items si
        JOIN products p ON si.product_id = p.id
        JOIN sales s ON si.sale_id = s.id
        WHERE s.sale_date BETWEEN ? AND ? AND s.training_mode = 0
        GROUP BY p.description
        ORDER BY quantity_sold DESC
    '''
    top_products_rows = conn.execute(top_products_query, params).fetchall()

    conn.close()

    # Conversão de centavos para float
    total_revenue_cents = general_summary_row['total_revenue']
    total_revenue = to_reais(total_revenue_cents)
    total_sales_count = general_summary_row['total_sales_count']
    average_ticket = total_revenue / total_sales_count if total_sales_count > 0 else 0

    payment_methods_list = []
    for row in payment_methods_rows:
        method = dict(row)
        if method['payment_method'] == 'Dinheiro':
            method['total'] -= total_change_cents
        method['total'] = to_reais(method['total'])
        payment_methods_list.append(method)

    top_products_list = []
    for row in top_products_rows:
        product = dict(row)
        product['revenue'] = to_reais(product['revenue'])
        top_products_list.append(product)

    return {
        'total_revenue': total_revenue,
        'total_sales_count': total_sales_count,
        'average_ticket': average_ticket,
        'payment_methods': payment_methods_list,
        'top_products': top_products_list
    }

def get_credit_payments_by_period(start_date, end_date):
    """Busca todos os pagamentos de fiados em um período."""
    conn = get_db_connection()
    start_datetime = f'{start_date} 00:00:00'
    end_datetime = f'{end_date} 23:59:59'
    rows = conn.execute('''
        SELECT cp.payment_method, SUM(cp.amount_paid) as total_paid
        FROM credit_payments cp
        WHERE cp.payment_date BETWEEN ? AND ?
        GROUP BY cp.payment_method
    ''', (start_datetime, end_datetime)).fetchall()
    conn.close()
    payments = []
    for row in rows:
        payment = dict(row)
        payment['total_paid'] = to_reais(payment['total_paid'])
        payments.append(payment)
    return payments

def get_credit_sales_by_period(start_date, end_date):
    """Busca todas as vendas a crédito criadas em um período."""
    conn = get_db_connection()
    start_datetime = f'{start_date} 00:00:00'
    end_datetime = f'{end_date} 23:59:59'
    rows = conn.execute('''
        SELECT cs.*, c.name as customer_name
        FROM credit_sales cs
        JOIN customers c ON cs.customer_id = c.id
        WHERE cs.created_date BETWEEN ? AND ?
    ''', (start_datetime, end_datetime)).fetchall()
    conn.close()
    sales = []
    for row in rows:
        sale = dict(row)
        sale['amount'] = to_reais(sale['amount'])
        sales.append(sale)
    return sales

def get_overdue_accounts_report():
    """Retorna uma lista de todos os clientes com fiados vencidos."""
    conn = get_db_connection()
    today = datetime.now().date()
    rows = conn.execute(f"""
        SELECT
            c.id as customer_id, c.name as customer_name, c.phone,
            cs.id as credit_sale_id, cs.amount, cs.due_date,
            (SELECT COALESCE(SUM(amount_paid), 0) FROM credit_payments WHERE credit_sale_id = cs.id) as total_paid_cents
        FROM credit_sales cs
        JOIN customers c ON cs.customer_id = c.id
        WHERE cs.status IN ('pending', 'partially_paid') AND cs.due_date < '{today}'
        ORDER BY cs.due_date ASC
    """).fetchall()
    conn.close()
    report = []
    for row in rows:
        entry = dict(row)
        amount = to_reais(entry['amount'])
        paid = to_reais(entry['total_paid_cents'])
        balance_due = amount - paid
        due_date = datetime.strptime(entry['due_date'], '%Y-%m-%d').date()
        days_overdue = (today - due_date).days
        entry['balance_due'] = balance_due
        entry['days_overdue'] = days_overdue
        report.append(entry)
    return report

def get_customer_abc_curve():
    """Retorna o ranking de clientes por valor total de compras (incluindo fiados)."""
    conn = get_db_connection()
    rows = conn.execute('''
        SELECT
            c.id, c.name, c.phone,
            COALESCE(SUM(cs.amount), 0) as total_credit_amount
        FROM customers c
        LEFT JOIN credit_sales cs ON c.id = cs.customer_id
        GROUP BY c.id
        ORDER BY total_credit_amount DESC
    ''').fetchall()
    conn.close()
    report = []
    total_overall = sum(row['total_credit_amount'] for row in rows)
    cumulative_percentage = 0
    for row in rows:
        entry = dict(row)
        amount = to_reais(entry['total_credit_amount'])
        percentage = (entry['total_credit_amount'] / total_overall * 100) if total_overall > 0 else 0
        cumulative_percentage += percentage
        entry['total_amount'] = amount
        entry['percentage'] = percentage
        entry['cumulative_percentage'] = cumulative_percentage
        if cumulative_percentage <= 80:
            entry['classification'] = 'A'
        elif cumulative_percentage <= 95:
            entry['classification'] = 'B'
        else:
            entry['classification'] = 'C'
        report.append(entry)
    return report

def get_monthly_credit_summary():
    """Retorna o total a receber e o total recebido no mês corrente."""
    conn = get_db_connection()
    start_of_month = datetime.now().date().replace(day=1).isoformat()
    total_paid_cents = conn.execute(
        f"SELECT COALESCE(SUM(amount_paid), 0) FROM credit_payments WHERE payment_date >= '{start_of_month}'"
    ).fetchone()[0]
    # Corrigido para somar os saldos individuais em vez de totais brutos
    total_due_cents = conn.execute('''
        SELECT COALESCE(SUM(cs.amount - (SELECT COALESCE(SUM(cp.amount_paid), 0) FROM credit_payments cp WHERE cp.credit_sale_id = cs.id)), 0)
        FROM credit_sales cs
        WHERE cs.status IN ('pending', 'partially_paid')
    ''').fetchone()[0]
    conn.close()
    return {
        'total_paid_month': to_reais(total_paid_cents),
        'total_due': to_reais(total_due_cents)
    }

def get_overdue_evolution():
    """
    Calcula o valor total vencido acumulado para cada um dos últimos 30 dias.
    Retorna uma lista de dicionários com 'date' e 'amount'.
    """
    conn = get_db_connection()
    evolution_data = []
    today = datetime.now().date()

    for i in range(29, -1, -1):
        current_date = today - timedelta(days=i)
        current_date_str = current_date.isoformat()

        # Query para obter o saldo devedor total de todas as vendas que estavam vencidas na data 'current_date'
        query = """
            SELECT COALESCE(SUM(balance_due_cents), 0)
            FROM (
                SELECT
                    cs.amount - (
                        SELECT COALESCE(SUM(cp.amount_paid), 0)
                        FROM credit_payments cp
                        WHERE cp.credit_sale_id = cs.id AND DATE(cp.payment_date) <= ?
                    ) as balance_due_cents
                FROM credit_sales cs
                WHERE
                    cs.due_date IS NOT NULL AND cs.due_date < ?
                    AND cs.status IN ('pending', 'partially_paid')
            )
            WHERE balance_due_cents > 0
        """
        
        cursor = conn.cursor()
        cursor.execute(query, (current_date_str, current_date_str))
        total_overdue_cents = cursor.fetchone()[0]
        
        evolution_data.append({
            'date': current_date_str,
            'amount': to_reais(total_overdue_cents)
        })
        
    conn.close()
    return evolution_data
