import sqlite3
import os
import hashlib
import shutil
from datetime import datetime
from decimal import Decimal, InvalidOperation
from utils import to_cents, to_reais, get_data_path
import logging
import functools
from typing import Optional, Dict, Any

DB_FILE = get_data_path('pdv.db')

def get_db_connection():
    """Cria e retorna uma conexão com o banco de dados."""
    conn = sqlite3.connect(DB_FILE)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode=WAL") # Melhora a concorrência e escrita
    conn.row_factory = sqlite3.Row
    return conn

def create_tables():
    """Cria as tabelas do banco de dados se elas não existirem."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Tabelas existentes
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS product_groups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            description TEXT NOT NULL,
            barcode TEXT UNIQUE,
            price INTEGER NOT NULL,
            stock INTEGER NOT NULL,
            quantity INTEGER NOT NULL DEFAULT 0,
            sale_type TEXT NOT NULL CHECK(sale_type IN ('unit', 'weight')),
            group_id INTEGER,
            FOREIGN KEY (group_id) REFERENCES product_groups (id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS payment_methods (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE
        )
    ''')

    # Novas tabelas para sistema de usuários
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('operador', 'gerente')),
            active BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            login_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            logout_time TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')

    # Novas tabelas para controle de caixa
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cash_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            open_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            close_time TIMESTAMP,
            initial_amount INTEGER NOT NULL,
            final_amount INTEGER,
            expected_amount INTEGER,
            difference INTEGER,
            status TEXT NOT NULL DEFAULT 'open' CHECK(status IN ('open', 'closed')),
            observations TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cash_movements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            type TEXT NOT NULL CHECK(type IN ('suprimento', 'sangria')),
            amount INTEGER NOT NULL,
            reason TEXT NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            authorized_by_id INTEGER,
            FOREIGN KEY (session_id) REFERENCES cash_sessions (id),
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (authorized_by_id) REFERENCES users (id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cash_counts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            denomination TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            total_value INTEGER NOT NULL,
            FOREIGN KEY (session_id) REFERENCES cash_sessions (id)
        )
    ''')

    # Tabela de vendas modificada para incluir sessão de caixa e usuário
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sale_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            total_amount INTEGER NOT NULL,
            user_id INTEGER,
            cash_session_id INTEGER,
            training_mode BOOLEAN DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (cash_session_id) REFERENCES cash_sessions (id)
        )
    ''')

    # Nova tabela para armazenar pagamentos individuais
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sale_payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sale_id INTEGER NOT NULL,
            payment_method TEXT NOT NULL,
            amount INTEGER NOT NULL,
            FOREIGN KEY (sale_id) REFERENCES sales (id) ON DELETE CASCADE
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sale_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sale_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            quantity REAL NOT NULL,
            unit_price INTEGER NOT NULL,
            total_price INTEGER NOT NULL,
            FOREIGN KEY (sale_id) REFERENCES sales (id),
            FOREIGN KEY (product_id) REFERENCES products (id)
        )
    ''')

    # Tabela de auditoria
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            action TEXT NOT NULL,
            table_name TEXT NOT NULL,
            record_id INTEGER,
            old_values TEXT,
            new_values TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')

    # --- Criação de Índices Otimizados ---
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_products_barcode ON products (barcode);')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_sales_sale_date ON sales (sale_date);')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_sales_date_user ON sales (sale_date, user_id);')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_sale_items_sale_id ON sale_items (sale_id);')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_sale_items_product_id ON sale_items (product_id);')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_products_group_id ON products (group_id);')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_sales_user_id ON sales (user_id);')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_sales_cash_session_id ON sales (cash_session_id);')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_sales_training_mode ON sales (training_mode);')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_cash_sessions_status ON cash_sessions (status);')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_cash_sessions_user_date ON cash_sessions (user_id, open_time);')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_audit_log_timestamp ON audit_log (timestamp);')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_audit_log_user_action ON audit_log (user_id, action);')

    # Criar índice adicional para produtos ativos se a coluna existir
    try:
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_products_active ON products (active, stock);')
    except sqlite3.OperationalError:
        # Coluna 'active' não existe, ignorar índice
        pass

    # Criar usuário administrador padrão se não existir
    cursor.execute('SELECT COUNT(*) FROM users WHERE role = "gerente"')
    if cursor.fetchone()[0] == 0:
        admin_password = hash_password('admin123')
        cursor.execute('''
            INSERT INTO users (username, password_hash, role)
            VALUES (?, ?, ?)
        ''', ('admin', admin_password, 'gerente'))
        logging.info("Usuário administrador criado: admin / admin123")

    # Criar tabela de configurações se não existir
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT NOT NULL UNIQUE,
            value TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Inserir configurações padrão do WhatsApp se não existirem
    whatsapp_configs = [
        ('whatsapp_notifications_enabled', 'false'),
        ('whatsapp_notification_number', ''),
        ('whatsapp_manager_numbers', ''),
        ('whatsapp_notifications_globally_enabled', 'true')
    ]

    for key, value in whatsapp_configs:
        cursor.execute('''
            INSERT OR IGNORE INTO settings (key, value)
            VALUES (?, ?)
        ''', (key, value))

    # Inserir formas de pagamento padrão se não existirem
    default_payment_methods = ['Dinheiro', 'PIX', 'Débito', 'Crédito']
    for method in default_payment_methods:
        cursor.execute('INSERT OR IGNORE INTO payment_methods (name) VALUES (?)', (method,))

    conn.commit()
    conn.close()
    logging.info("Banco de dados e tabelas criados com sucesso.")

def add_product(description, barcode, price, stock, sale_type, group_id):
    """Adiciona um novo produto ao banco de dados."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        price_decimal = Decimal(str(price)).quantize(Decimal('0.01'))
        price_in_cents = to_cents(price_decimal)

        # Converte o estoque para INTEGER (multiplicando por 1000 para 3 casas decimais)
        stock_decimal = Decimal(str(stock))
        stock_integer = int(stock_decimal * 1000)

        cursor.execute(
            'INSERT INTO products (description, barcode, price, stock, quantity, sale_type, group_id) VALUES (?, ?, ?, ?, ?, ?, ?)',
            (description, barcode, price_in_cents, stock_integer, stock_integer, sale_type, group_id)
        )
        conn.commit()
        return True, cursor.lastrowid
    except sqlite3.IntegrityError:
        return False, "Erro: Já existe um produto com este código de barras."
    except sqlite3.Error as e:
        return False, f"Erro de banco de dados ao adicionar produto: {e}"
    finally:
        conn.close()

def get_all_products():
    conn = get_db_connection()
    rows = conn.execute('SELECT p.*, g.name as group_name FROM products p LEFT JOIN product_groups g ON p.group_id = g.id ORDER BY p.description').fetchall()
    conn.close()
    products = []
    for row in rows:
        product = dict(row)
        if product['price'] is not None:
            product['price'] = to_reais(product['price'])
        # Converte stock de INTEGER para decimal (dividindo por 1000)
        if product['stock'] is not None:
            product['stock'] = Decimal(product['stock']) / Decimal('1000')
        products.append(product)
    return products

@functools.lru_cache(maxsize=100)
def get_product_by_barcode_cached(barcode: str):
    """Busca produto por código de barras com cache LRU."""
    return get_product_by_barcode(barcode)

def get_product_by_barcode(barcode):
    """Busca produto por código de barras."""
    conn = get_db_connection()
    row = conn.execute('SELECT * FROM products WHERE barcode = ?', (barcode,)).fetchone()
    conn.close()
    if row:
        product = dict(row)
        if product['price'] is not None:
            product['price'] = to_reais(product['price'])
        return product
    return None

def clear_product_cache():
    """Limpa cache de produtos."""
    get_product_by_barcode_cached.cache_clear()
    logging.info("Cache de produtos limpo")

def get_cache_stats() -> Dict[str, Any]:
    """Retorna estatísticas do cache."""
    cache_info = get_product_by_barcode_cached.cache_info()
    return {
        'cache_hits': cache_info.hits,
        'cache_misses': cache_info.misses,
        'cache_size': cache_info.currsize,
        'max_size': cache_info.maxsize
    }

def update_product(product_id, description, barcode, price, stock, sale_type, group_id):
    """Atualiza os dados de um produto existente."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        price_decimal = Decimal(str(price)).quantize(Decimal('0.01'))
        price_in_cents = to_cents(price_decimal)

        # Converte o estoque para INTEGER (multiplicando por 1000 para 3 casas decimais)
        stock_decimal = Decimal(str(stock))
        stock_integer = int(stock_decimal * 1000)

        cursor.execute('''
            UPDATE products
            SET description = ?, barcode = ?, price = ?, stock = ?, quantity = ?, sale_type = ?, group_id = ?
            WHERE id = ?
        ''', (description, barcode, price_in_cents, stock_integer, stock_integer, sale_type, group_id, product_id))
        conn.commit()
        return True, "Produto atualizado com sucesso."
    except sqlite3.IntegrityError:
        return False, "Erro: O código de barras informado já pertence a outro produto."
    except sqlite3.Error as e:
        return False, f"Erro de banco de dados ao atualizar produto: {e}"
    finally:
        conn.close()

def delete_product(product_id):
    """Deleta um produto do banco de dados."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('DELETE FROM products WHERE id = ?', (product_id,))
        conn.commit()
        if cursor.rowcount > 0:
            return True, "Produto deletado com sucesso."
        return False, "Produto não encontrado."
    except sqlite3.IntegrityError:
        return False, "Erro: Este produto não pode ser deletado pois está associado a vendas existentes."
    except sqlite3.Error as e:
        return False, f"Erro de banco de dados ao deletar produto: {e}"
    finally:
        conn.close()

def update_product_price(barcode, new_price):
    """Atualiza o preço de um produto pelo código de barras."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        price_decimal = Decimal(str(new_price)).quantize(Decimal('0.01'))
        price_in_cents = to_cents(price_decimal)
        cursor.execute('UPDATE products SET price = ? WHERE barcode = ?', (price_in_cents, barcode))
        conn.commit()
        if cursor.rowcount > 0:
            return True, "Preço atualizado com sucesso."
        return False, "Produto com o código de barras não encontrado."
    except sqlite3.Error as e:
        conn.rollback()
        return False, f"Erro de banco de dados ao atualizar preço: {e}"
    finally:
        conn.close()

# --- Funções de Vendas ---

def register_sale(total_amount, payment_method, items):
    """[DEPRECATED] Registra uma venda. Use register_sale_with_user para novos desenvolvimentos."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        total_amount_cents = to_cents(total_amount)
        cursor.execute('INSERT INTO sales (total_amount, payment_method) VALUES (?, ?)', (total_amount_cents, payment_method))
        sale_id = cursor.lastrowid
        for item in items:
            unit_price_cents = to_cents(item['unit_price'])
            total_price_cents = to_cents(item['total_price'])
            cursor.execute('INSERT INTO sale_items (sale_id, product_id, quantity, unit_price, total_price) VALUES (?, ?, ?, ?, ?)', 
                         (sale_id, item['id'], item['quantity'], unit_price_cents, total_price_cents))
            
            # Apenas atualiza o estoque para itens vendidos por unidade.
            if item.get('sale_type') == 'unit':
                cursor.execute('UPDATE products SET stock = stock - ? WHERE id = ?', (item['quantity'], item['id']))
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

# Adicione esta função em 'database.py' na seção de Funções de Vendas

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

def get_sales_with_payment_methods_by_period(start_date, end_date):
    """
    Retorna todas as vendas dentro de um período de datas específico.
    Usa uma única consulta otimizada com LEFT JOIN e GROUP_CONCAT.
    """
    conn = get_db_connection()

    # Adiciona o horário para pegar o dia inteiro
    start_datetime = f'{start_date} 00:00:00'
    end_datetime = f'{end_date} 23:59:59'

    query = '''
        SELECT 
            s.id, s.sale_date, s.total_amount, s.user_id, s.cash_session_id, s.training_mode,
            u.username,
            GROUP_CONCAT(sp.payment_method, ', ') as payment_methods_str
        FROM sales s
        LEFT JOIN sale_payments sp ON s.id = sp.sale_id
        LEFT JOIN users u ON s.user_id = u.id
        WHERE s.sale_date BETWEEN ? AND ? AND s.training_mode = 0
        GROUP BY s.id
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

# --- Funções para Grupos de Produtos ---

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
        cursor.execute('UPDATE product_groups SET name = ? WHERE id = ?', (name, group_id))
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

# --- Funções para Formas de Pagamento ---

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


# --- Funções de Usuários ---

def hash_password(password):
    """Gera hash da senha usando SHA-256."""
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(password, password_hash):
    """Verifica se a senha corresponde ao hash."""
    return hash_password(password) == password_hash

def authenticate_user(username, password):
    """Autentica usuário e retorna dados se válido."""
    conn = get_db_connection()
    user = conn.execute('''
        SELECT * FROM users 
        WHERE username = ? AND active = 1
    ''', (username,)).fetchone()
    conn.close()
    
    if user and verify_password(password, user['password_hash']):
        return dict(user)
    return None

def create_user(username, password, role):
    """Cria novo usuário."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        password_hash = hash_password(password)
        cursor.execute('''
            INSERT INTO users (username, password_hash, role) 
            VALUES (?, ?, ?)
        ''', (username, password_hash, role))
        conn.commit()
        return True, cursor.lastrowid
    except sqlite3.IntegrityError:
        return False, "Erro: Nome de usuário já existe."
    except sqlite3.Error as e:
        return False, f"Erro de banco de dados ao criar usuário: {e}"
    finally:
        conn.close()

def get_all_users():
    """Retorna todos os usuários."""
    conn = get_db_connection()
    users = conn.execute('SELECT id, username, role, active, created_at FROM users ORDER BY username').fetchall()
    conn.close()
    return users

def update_user(user_id, username=None, password=None, role=None, active=None):
    """Atualiza dados do usuário."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    updates = []
    params = []
    
    if username is not None:
        updates.append('username = ?')
        params.append(username)
    if password is not None and password.strip(): # Garante que não se atualize com senha vazia
        updates.append('password_hash = ?')
        params.append(hash_password(password))
    if role is not None:
        updates.append('role = ?')
        params.append(role)
    if active is not None:
        updates.append('active = ?')
        params.append(active)
    
    if not updates:
        return True, "Nenhuma alteração a ser feita."

    params.append(user_id)
    query = f'UPDATE users SET {", ".join(updates)} WHERE id = ?'
    
    try:
        cursor.execute(query, params)
        conn.commit()
        return True, "Usuário atualizado com sucesso."
    except sqlite3.IntegrityError:
        return False, "Erro: Nome de usuário já existe."
    except sqlite3.Error as e:
        return False, f"Erro de banco de dados ao atualizar usuário: {e}"
    finally:
        conn.close()

def log_user_session(user_id, action='login'):
    """Registra login/logout do usuário."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if action == 'login':
        cursor.execute('INSERT INTO user_sessions (user_id) VALUES (?)', (user_id,))
    elif action == 'logout':
        cursor.execute('''
            UPDATE user_sessions 
            SET logout_time = CURRENT_TIMESTAMP 
            WHERE user_id = ? AND logout_time IS NULL
        ''', (user_id,))
    
    conn.commit()
    conn.close()

# --- Funções de Controle de Caixa ---

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

        # Soma vendas em dinheiro usando a nova tabela sale_payments (valores já em centavos no DB)
        cash_sales_cents = cursor.execute('''
            SELECT COALESCE(SUM(sp.amount), 0) as total
            FROM sale_payments sp
            JOIN sales s ON sp.sale_id = s.id
            WHERE s.cash_session_id = ? AND sp.payment_method = 'Dinheiro' AND s.training_mode = 0
        ''', (session_id,)).fetchone()['total']

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

    return {
        'session': session_dict,
        'sales': sales_list,
        'movements': movements_list,
        'counts': counts_list,
        'total_revenue': total_revenue,
        'total_after_sangria': total_revenue - total_sangria
    }

# --- Funções de Backup ---

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

# --- Funções de Auditoria ---

def log_audit(user_id, action, table_name, record_id, old_values=None, new_values=None):
    """Registra ação na auditoria."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO audit_log (user_id, action, table_name, record_id, old_values, new_values)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (user_id, action, table_name, record_id, old_values, new_values))
    
    conn.commit()
    conn.close()

def get_audit_log(limit=100, user_id=None, action=None):
    """Retorna log de auditoria."""
    conn = get_db_connection()
    
    query = '''
        SELECT al.*, u.username 
        FROM audit_log al
        LEFT JOIN users u ON al.user_id = u.id
        WHERE 1=1
    '''
    params = []
    
    if user_id:
        query += ' AND al.user_id = ?'
        params.append(user_id)
    
    if action:
        query += ' AND al.action = ?'
        params.append(action)
    
    query += ' ORDER BY al.timestamp DESC LIMIT ?'
    params.append(limit)
    
    logs = conn.execute(query, params).fetchall()
    conn.close()
    
    return [dict(log) for log in logs]

# --- Funções de Vendas Modificadas ---

def register_sale_with_user(total_amount, payment_method, items, user_id=None, cash_session_id=None, training_mode=False):
    """Registra venda com informações de usuário e sessão."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Garante que o valor final seja um inteiro
        total_amount_cents = int(to_cents(total_amount))
        cursor.execute('''
            INSERT INTO sales (total_amount, user_id, cash_session_id, training_mode)
            VALUES (?, ?, ?, ?)
        ''', (total_amount_cents, user_id, cash_session_id, training_mode))

        sale_id = cursor.lastrowid

        for item in items:
            # Garante que os valores de preço também sejam inteiros
            unit_price_cents = int(to_cents(item['unit_price']))
            total_price_cents = int(to_cents(item['total_price']))
            quantity_float = float(item['quantity']) # Correção anterior mantida

            cursor.execute('''
                INSERT INTO sale_items (sale_id, product_id, quantity, unit_price, total_price)
                VALUES (?, ?, ?, ?, ?)
            ''', (sale_id, item['id'], quantity_float, unit_price_cents, total_price_cents))

            # Só atualiza estoque se não for modo treinamento e o item for vendido por unidade.
            if not training_mode and item.get('sale_type') == 'unit':
                # Verifica se há estoque suficiente
                stock_check = cursor.execute('SELECT stock FROM products WHERE id = ?', (item['id'],)).fetchone()
                if stock_check and stock_check[0] < item['quantity']:
                    raise sqlite3.Error(f"Estoque insuficiente para o produto: {item['description']}")

                cursor.execute('UPDATE products SET stock = stock - ? WHERE id = ?', (float(item['quantity']), item['id']))

        # Se payment_method for uma string (formato antigo), converte para lista de pagamentos
        if isinstance(payment_method, str):
            # Tenta fazer o parsing da string para extrair os pagamentos
            import re
            payment_pattern = r'(\w+):\s*R\$\s*([\d,]+)'
            matches = re.findall(payment_pattern, payment_method)

            if matches:
                # Se conseguiu extrair pagamentos da string, usa eles
                payments_list = []
                for method, amount_str in matches:
                    try:
                        amount_decimal = Decimal(amount_str.replace(',', '.'))
                        payments_list.append({'method': method, 'amount': amount_decimal})
                    except:
                        # Se não conseguir fazer o parsing, usa o método antigo
                        payments_list = [{'method': payment_method, 'amount': total_amount}]
            else:
                # Se não conseguiu extrair, usa o método antigo
                payments_list = [{'method': payment_method, 'amount': total_amount}]
        else:
            # Se já for uma lista (novo formato), usa diretamente
            payments_list = payment_method

        # Insere os pagamentos individuais na tabela sale_payments
        for payment in payments_list:
            payment_amount_cents = int(to_cents(payment['amount']))
            cursor.execute('''
                INSERT INTO sale_payments (sale_id, payment_method, amount)
                VALUES (?, ?, ?)
            ''', (sale_id, payment['method'], payment_amount_cents))

        conn.commit()

        if user_id:
            log_audit(user_id, 'SALE', 'sales', sale_id)

        return True, sale_id
    except sqlite3.Error as e:
        conn.rollback()
        return False, f"Erro ao registrar a venda: {e}"
    finally:
        conn.close()

def get_user_by_id(user_id):
    """Retorna dados do usuário pelo ID."""
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    conn.close()
    return dict(user) if user else None

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
        if item.get('total') is not None:
            item['total'] = to_reais(item['total'])
        summary.append(item)
    return summary

def get_payment_summary_by_sale(sale_id):
    """Retorna resumo de pagamentos para uma venda específica."""
    conn = get_db_connection()
    rows = conn.execute('''
        SELECT payment_method, amount
        FROM sale_payments
        WHERE sale_id = ?
        ORDER BY payment_method
    ''', (sale_id,)).fetchall()
    conn.close()

    summary = []
    for row in rows:
        item = dict(row)
        if item.get('amount') is not None:
            item['amount'] = to_reais(item['amount'])
        summary.append(item)
    return summary

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

# --- Funções de Relatórios ---

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

def get_stock_report():
    """Gera um relatório de níveis de estoque."""
    conn = get_db_connection()

    stock_levels_query = '''
        SELECT
            p.id,
            p.description,
            p.stock,
            p.sale_type,
            g.name as group_name
        FROM products p
        LEFT JOIN product_groups g ON p.group_id = g.id
        ORDER BY p.description
    '''
    stock_levels = conn.execute(stock_levels_query).fetchall()

    # Converter stock de INTEGER para decimal
    stock_levels_converted = []
    for row in stock_levels:
        item = dict(row)
        if item['stock'] is not None:
            item['stock'] = Decimal(item['stock']) / Decimal('1000')
        stock_levels_converted.append(item)

    # Poderíamos adicionar um limite configurável de estoque baixo
    low_stock_query = '''
        SELECT description, stock FROM products WHERE stock <= 5000 ORDER BY stock ASC
    '''
    low_stock_items = conn.execute(low_stock_query).fetchall()

    # Converter também os itens de baixo estoque
    low_stock_converted = []
    for row in low_stock_items:
        item = dict(row)
        if item['stock'] is not None:
            item['stock'] = Decimal(item['stock']) / Decimal('1000')
        low_stock_converted.append(item)

    conn.close()

    return {
        'stock_levels': stock_levels_converted,
        'low_stock_items': low_stock_converted
    }

def get_authorized_managers() -> list[str]:
    """Busca e retorna a lista de números de telefone de gerentes autorizados."""
    numbers_str = load_setting('whatsapp_manager_numbers', '')
    if not numbers_str:
        return []
    # Retorna uma lista de números limpos, sem espaços ou caracteres extras
    return [num.strip() for num in numbers_str.split(',') if num.strip()]

def set_global_notification_status(enabled: bool):
    """Ativa ou desativa globalmente o envio de notificações."""
    save_setting('whatsapp_notifications_globally_enabled', 'true' if enabled else 'false')

def are_notifications_globally_enabled() -> bool:
    """Verifica se as notificações estão globalmente ativadas."""
    return load_setting('whatsapp_notifications_globally_enabled', 'true') == 'true'

def get_cash_session_history(start_date=None, end_date=None, operator_id=None, limit=100):
    """Retorna um histórico de sessões de caixa fechadas com filtros opcionais."""
    conn = get_db_connection()
    
    params = []
    history_query = '''
        SELECT
            cs.id,
            cs.open_time,
            cs.close_time,
            cs.initial_amount,
            cs.expected_amount,
            cs.final_amount,
            cs.difference,
            u.username
        FROM cash_sessions cs
        LEFT JOIN users u ON cs.user_id = u.id
        WHERE cs.status = 'closed'
    '''
    
    if start_date:
        history_query += ' AND date(cs.close_time) >= ?'
        params.append(start_date)
    
    if end_date:
        history_query += ' AND date(cs.close_time) <= ?'
        params.append(end_date)
        
    if operator_id:
        history_query += ' AND cs.user_id = ?'
        params.append(operator_id)
        
    history_query += ' ORDER BY cs.close_time DESC LIMIT ?'
    params.append(limit)
    
    rows = conn.execute(history_query, params).fetchall()
    conn.close()
    
    history = []
    for row in rows:
        session = dict(row)
        session['open_time'] = _parse_datetime(session['open_time'])
        session['close_time'] = _parse_datetime(session['close_time'])
        for field in ['initial_amount', 'expected_amount', 'final_amount', 'difference']:
            if session.get(field) is not None:
                session[field] = to_reais(session[field])
        history.append(session)
    return history

# --- Funções de Configurações ---

def save_setting(key, value):
    """Salva ou atualiza uma configuração no banco de dados."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT OR REPLACE INTO settings (key, value, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
        ''', (key, str(value)))
        conn.commit()
        return True
    except sqlite3.Error as e:
        logging.error(f"Erro ao salvar configuração {key}: {e}", exc_info=True)
        return False
    finally:
        conn.close()

def load_setting(key, default_value=None):
    """Carrega uma configuração do banco de dados."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT value FROM settings WHERE key = ?', (key,))
        row = cursor.fetchone()
        if row:
            return row['value']
        return default_value
    except sqlite3.Error as e:
        logging.error(f"Erro ao carregar configuração {key}: {e}", exc_info=True)
        return default_value
    finally:
        conn.close()

# if __name__ == '__main__':
#     if os.path.exists(DB_FILE):
#         os.remove(DB_FILE)
#         print(f"Banco de dados antigo '{DB_FILE}' removido.")
#     print(f"Criando novo banco de dados '{DB_FILE}'...")
#     create_tables()
