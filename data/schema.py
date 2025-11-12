import logging
import hashlib
from .connection import get_db_connection

def create_tables():
    """Cria as tabelas do banco de dados se elas não existirem."""
    logging.info("Iniciando a criação de tabelas...")
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        logging.info("Criando tabela product_groups...")
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS product_groups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE
            )
        ''')

        logging.info("Criando tabela products...")
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

        logging.info("Criando tabela payment_methods...")
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS payment_methods (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE
            )
        ''')

        logging.info("Criando tabela users...")
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

        logging.info("Criando tabela user_sessions...")
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                login_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                logout_time TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')

        logging.info("Criando tabela cash_sessions...")
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

        logging.info("Criando tabela cash_movements...")
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

        logging.info("Criando tabela cash_counts...")
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

        logging.info("Criando tabela sales...")
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sales (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sale_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                total_amount INTEGER NOT NULL,
                change_amount INTEGER NOT NULL DEFAULT 0,
                user_id INTEGER,
                cash_session_id INTEGER,
                training_mode BOOLEAN DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users (id),
                FOREIGN KEY (cash_session_id) REFERENCES cash_sessions (id)
            )
        ''')

        logging.info("Criando tabela sale_payments...")
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sale_payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sale_id INTEGER NOT NULL,
                payment_method TEXT NOT NULL,
                amount INTEGER NOT NULL,
                FOREIGN KEY (sale_id) REFERENCES sales (id) ON DELETE CASCADE
            )
        ''')

        logging.info("Criando tabela sale_items...")
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

        logging.info("Criando tabela audit_log...")
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

        logging.info("Criando tabela customers...")
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS customers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                cpf TEXT UNIQUE,
                phone TEXT,
                address TEXT,
                credit_limit INTEGER DEFAULT 0, -- Limite de crédito em centavos. 0 = sem limite.
                is_blocked BOOLEAN DEFAULT 0, -- Para bloquear clientes inadimplentes
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        logging.info("Criando tabela credit_sales...")
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS credit_sales (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id INTEGER NOT NULL,
                sale_id INTEGER, -- Venda original (opcional, mas recomendado)
                amount INTEGER NOT NULL, -- Valor total do fiado em centavos
                status TEXT DEFAULT 'pending' CHECK(status IN ('pending', 'partially_paid', 'paid', 'cancelled')),
                observations TEXT,
                created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                due_date DATE,
                user_id INTEGER NOT NULL,
                FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE RESTRICT,
                FOREIGN KEY (sale_id) REFERENCES sales(id) ON DELETE SET NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')

        logging.info("Criando tabela credit_payments...")
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS credit_payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                credit_sale_id INTEGER NOT NULL,
                amount_paid INTEGER NOT NULL, -- Valor pago em centavos
                payment_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                user_id INTEGER NOT NULL,
                payment_method TEXT NOT NULL, -- Dinheiro, PIX, Cartão, etc.
                cash_session_id INTEGER, -- Sessão de caixa em que o pagamento foi recebido
                FOREIGN KEY (credit_sale_id) REFERENCES credit_sales(id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (cash_session_id) REFERENCES cash_sessions(id) ON DELETE SET NULL
            )
        ''')


        logging.info("Criando tabela estoque_grupos...")
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS estoque_grupos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT UNIQUE NOT NULL
            )
        ''')

        logging.info("Criando tabela estoque_itens...")
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS estoque_itens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                codigo TEXT UNIQUE NOT NULL,
                nome TEXT NOT NULL,
                grupo_id INTEGER NOT NULL,
                estoque_atual INTEGER NOT NULL,
                estoque_minimo INTEGER NOT NULL DEFAULT 0,
                unidade_medida TEXT,
                FOREIGN KEY (grupo_id) REFERENCES estoque_grupos (id)
            )
        ''')
        
        logging.info("Criando índices...")
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
        cursor.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_customers_name_phone ON customers(name, phone);')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_credit_sales_customer_id ON credit_sales(customer_id);')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_credit_sales_status ON credit_sales(status);')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_products_barcode_active ON products (barcode, stock);')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_products_group_active ON products (group_id, stock);')

        logging.info("Verificando/criando usuário admin...")
        cursor.execute('SELECT COUNT(*) FROM users WHERE role = "gerente"')
        if cursor.fetchone()[0] == 0:
            admin_password = hash_password('admin123')
            cursor.execute('''
                INSERT INTO users (username, password_hash, role)
                VALUES (?, ?, ?)
            ''', ('admin', admin_password, 'gerente'))
            logging.info("Usuário administrador criado: admin / admin123")

        logging.info("Criando tabela settings...")
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT NOT NULL UNIQUE,
                value TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        logging.info("Inserindo configurações padrão do WhatsApp...")
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

        logging.info("Inserindo formas de pagamento padrão...")
        default_payment_methods = ['Dinheiro', 'PIX', 'Débito', 'Crédito']
        for method in default_payment_methods:
            cursor.execute('INSERT OR IGNORE INTO payment_methods (name) VALUES (?)', (method,))

        conn.commit()
        logging.info("Criação de tabelas concluída com sucesso.")

    except Exception as e:
        logging.error(f"Erro durante a criação de tabelas: {e}", exc_info=True)
        raise # Re-levanta a exceção para que a main.py possa capturá-la
    finally:
        pass

def apply_automatic_fixes():
    """
    Procura e remove ativamente problemas conhecidos do schema que
    não podem ser resolvidos por migrações SQL simples, como triggers órfãos.
    """
    logging.info("Verificando correções automáticas do banco de dados...")

    problematic_triggers = []
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Verifica a existência de triggers que referenciam a tabela temporária
        cursor.execute("SELECT name, sql FROM sqlite_master WHERE type = 'trigger'")
        all_triggers = cursor.fetchall()

        for trigger in all_triggers:
            name = trigger['name']
            sql_definition = trigger['sql']

            # Procura a string exata do erro
            if sql_definition and 'credit_sales_temp_migration' in sql_definition:
                problematic_triggers.append(name)
                logging.warning(f"Encontrado trigger problemático '{name}' referenciando 'credit_sales_temp_migration'.")

        if not problematic_triggers:
            logging.info("Nenhum trigger problemático encontrado.")
            return

        # Remove os triggers encontrados
        for trigger_name in problematic_triggers:
            logging.info(f"Removendo trigger órfão: {trigger_name}")
            cursor.execute(f"DROP TRIGGER IF EXISTS {trigger_name}")

        conn.commit()
        logging.info("Correções automáticas do banco de dados aplicadas com sucesso.")

    except sqlite3.Error as e:
        logging.error(f"Erro de banco de dados ao aplicar correção automática: {e}")
        conn.rollback()
    finally:
        pass

def hash_password(password):
    """Gera hash da senha usando SHA-256."""
    return hashlib.sha256(password.encode()).hexdigest()
