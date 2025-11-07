#!/usr/bin/env python3
"""
Script de migração para atualizar o banco de dados do PDV
para o novo sistema de múltiplos pagamentos por venda.

Este script:
1. Cria a nova tabela sale_payments
2. Migra os dados existentes da coluna payment_method para a nova tabela
3. Remove a coluna payment_method da tabela sales
"""

import sqlite3
import re
from decimal import Decimal
from utils import get_data_path
import logging

def _add_column_if_not_exists(cursor, table_name, column_name, column_def):
    """Adiciona uma coluna a uma tabela se ela ainda não existir."""
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = [row['name'] for row in cursor.fetchall()]
    if column_name not in columns:
        logging.info(f"Adicionando coluna '{column_name}' à tabela '{table_name}'...")
        cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_def}")
    else:
        logging.info(f"Coluna '{column_name}' já existe em '{table_name}'. Pulando.")


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

DB_FILE = get_data_path('pdv.db')

def get_db_connection():
    """Cria e retorna uma conexão com o banco de dados."""
    conn = sqlite3.connect(DB_FILE)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn

def migrate_database():
    """Executa a migração do banco de dados."""
    logging.info("Iniciando migração do banco de dados...")

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Verifica se a tabela sales ainda tem a coluna payment_method
        cursor.execute("PRAGMA table_info(sales)")
        columns = cursor.fetchall()
        has_payment_method_column = any(col['name'] == 'payment_method' for col in columns)

        if not has_payment_method_column:
            logging.info("✅ Migração já foi executada anteriormente. Nenhuma ação necessária.")
            return True

        logging.info("📋 Iniciando processo de migração...")

        # 1. Criar nova tabela sale_payments
        logging.info("   Criando tabela sale_payments...")
        cursor.execute('''
            CREATE TABLE sale_payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sale_id INTEGER NOT NULL,
                payment_method TEXT NOT NULL,
                amount INTEGER NOT NULL,
                FOREIGN KEY (sale_id) REFERENCES sales (id) ON DELETE CASCADE
            )
        ''')

        # 2. Migrar dados existentes
        logging.info("   Migrando dados existentes...")

        # Buscar todas as vendas que têm payment_method
        cursor.execute('''
            SELECT id, total_amount, payment_method
            FROM sales
            WHERE payment_method IS NOT NULL AND payment_method != ''
        ''')

        sales_to_migrate = cursor.fetchall()

        for sale in sales_to_migrate:
            sale_id = sale['id']
            total_amount = sale['total_amount']
            payment_method_str = sale['payment_method']

            # Fazer o parsing da string de pagamento
            payments_list = parse_payment_string(payment_method_str, total_amount)

            # Inserir pagamentos na nova tabela
            for payment in payments_list:
                payment_amount_cents = int(payment['amount'] * 100)  # Converter para centavos
                cursor.execute('''
                    INSERT INTO sale_payments (sale_id, payment_method, amount)
                    VALUES (?, ?, ?)
                ''', (sale_id, payment['method'], payment_amount_cents))

        # 3. Reconstruir a tabela sales sem a coluna payment_method (método seguro)
        logging.info("   Reconstruindo a tabela sales sem a coluna payment_method...")

        # 3.1. Renomear a tabela sales original
        cursor.execute('ALTER TABLE sales RENAME TO sales_old')

        # 3.2. Criar a nova tabela sales com o esquema atualizado
        cursor.execute('''
            CREATE TABLE sales (
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

        # 3.3. Copiar os dados da tabela antiga para a nova
        # Obter a lista de colunas da tabela antiga para garantir a compatibilidade
        cursor.execute("PRAGMA table_info(sales_old)")
        old_columns = [col['name'] for col in cursor.fetchall()]
        columns_to_copy = [col for col in old_columns if col != 'payment_method']
        columns_str = ", ".join(columns_to_copy)

        cursor.execute(f'''
            INSERT INTO sales ({columns_str})
            SELECT {columns_str}
            FROM sales_old
        ''')

        # 3.4. Deletar a tabela antiga
        cursor.execute('DROP TABLE sales_old')

        # 4. Criar índice para a nova tabela
        logging.info("   Criando índices...")
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_sale_payments_sale_id ON sale_payments (sale_id)')

        conn.commit()
        logging.info("✅ Migração concluída com sucesso!")

        # Verificar se há dados migrados
        cursor.execute('SELECT COUNT(*) FROM sale_payments')
        migrated_count = cursor.fetchone()[0]

        logging.info(f"📊 {migrated_count} registros de pagamento migrados.")

        return True

    except sqlite3.Error as e:
        logging.error(f"❌ Erro durante a migração: {e}", exc_info=True)
        conn.rollback()
        return False
    finally:
        conn.close()

def parse_payment_string(payment_string, total_amount):
    """
    Faz o parsing de uma string de pagamento no formato antigo
    e retorna uma lista de dicionários com os pagamentos.
    """
    payments_list = []

    # Padrão para encontrar métodos e valores: "Método: R$ valor"
    payment_pattern = r'(\w+):\s*R\$\s*([\d,]+)'
    matches = re.findall(payment_pattern, payment_string)

    if matches:
        # Se conseguiu extrair pagamentos da string
        for method, amount_str in matches:
            try:
                amount_decimal = Decimal(amount_str.replace(',', '.'))
                payments_list.append({'method': method, 'amount': amount_decimal})
            except:
                logging.warning(f"   ⚠️  Erro ao fazer parsing do pagamento: {method}: R$ {amount_str}")
                continue

        # Verificar se a soma dos pagamentos é igual ao total
        total_payments = sum(p['amount'] for p in payments_list)
        if abs(total_payments - Decimal(str(total_amount)) / 100) > Decimal('0.01'):
            logging.warning(f"   ⚠️  Diferença de valor detectada na venda. Total: {total_amount/100}, Pagamentos: {total_payments}")
    else:
        # Se não conseguiu extrair, assume que é um único método de pagamento
        payments_list = [{'method': payment_string, 'amount': Decimal(str(total_amount)) / 100}]

    return payments_list

def _run_migration_003_add_sync_columns():
    """
    Migração 003: Adiciona colunas para sincronização com a API web (Supabase).
    """
    logging.info("Executando migração 003: Adicionando colunas de sincronização...")
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Tabelas que precisam ser sincronizadas
        tables_to_sync = [
            'product_groups',
            'products',
            'payment_methods',
            'users',
            'customers',
            'sales',
            'sale_items',
            'credit_sales',
            'credit_payments',
            'estoque_grupos',
            'estoque_itens'
        ]

        for table in tables_to_sync:
            logging.info(f"Processando tabela: {table}")

            # 1. id_web: Armazena o ID do registro na nuvem (Supabase)
            _add_column_if_not_exists(cursor, table, 'id_web', 'TEXT')

            # Criar um índice único em id_web. Em SQLite, índices únicos permitem múltiplos valores NULL,
            # o que resolve o problema de adicionar a coluna a uma tabela com dados existentes.
            index_name = f"idx_{table}_id_web_unique"
            cursor.execute(f"CREATE UNIQUE INDEX IF NOT EXISTS {index_name} ON {table}(id_web)")

            # 2. sync_status: Controla o estado de sincronização
            #    'pending_create': Novo local, precisa ser enviado.
            #    'pending_update': Atualizado local, precisa ser enviado.
            #    'synced': Sincronizado.
            # Marcamos todos os registros existentes como 'pending_create'
            # para forçar uma sincronização inicial completa na primeira vez.
            _add_column_if_not_exists(cursor, table, 'sync_status', "TEXT NOT NULL DEFAULT 'pending_create'")

            # 3. last_modified_at: Timestamp da última modificação local
            _add_column_if_not_exists(cursor, table, 'last_modified_at', "TIMESTAMP NOT NULL DEFAULT '2000-01-01 00:00:00'")

            # 4. Criar Trigger para atualizar 'last_modified_at' em cada UPDATE
            trigger_name = f"trg_{table}_update_last_modified"
            cursor.execute(f"DROP TRIGGER IF EXISTS {trigger_name}")
            cursor.execute(f"""
                CREATE TRIGGER {trigger_name}
                AFTER UPDATE ON {table}
                FOR EACH ROW
                BEGIN
                    UPDATE {table}
                    SET last_modified_at = CURRENT_TIMESTAMP
                    WHERE id = OLD.id;
                END;
            """)

            logging.info(f"Tabela '{table}' atualizada para sincronização.")
        
        conn.commit()
        logging.info("Migração 003 concluída com sucesso.")
    except sqlite3.Error as e:
        logging.error(f"   ❌ Erro na migração 003: {e}")
        conn.rollback()
    finally:
        conn.close()
def is_credit_sales_constraint_broken():
    """Verifica se a constraint de status da tabela credit_sales está quebrada."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("BEGIN TRANSACTION")
        # Tenta inserir um valor que falharia na constraint antiga
        cursor.execute("""
            INSERT INTO credit_sales (id, customer_id, amount, status, user_id) 
            VALUES (-99, -1, 0, 'partially_paid', -1)
        """)
        # Se funcionou, a constraint está correta. Desfaz e retorna False.
        cursor.execute("ROLLBACK")
        return False
    except sqlite3.IntegrityError as e:
        cursor.execute("ROLLBACK")
        # Se o erro for o esperado, a migração é necessária
        if "CHECK constraint failed" in str(e):
            return True
        # Outro erro de integridade (ex: UNIQUE), a constraint de status está ok
        return False
    except sqlite3.OperationalError as e:
        # A tabela pode não existir ainda, então não há o que migrar
        if "no such table" in str(e):
            return False
        raise e # Outro erro operacional inesperado
    finally:
        conn.close()

def is_any_migration_needed():
    """Verifica se QUALQUER migração pendente é necessária."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Verifica se a tabela sales existe
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='sales'")
        if not cursor.fetchone():
            return False # Tabela não existe, será criada do zero, sem migração

        cursor.execute("PRAGMA table_info(sales)")
        columns = [col['name'] for col in cursor.fetchall()]
        
        # Verificação 1: Coluna payment_method (precisa ser removida)
        if 'payment_method' in columns:
            return True

        # Verificação 2: Coluna change_amount (precisa ser adicionada)
        if 'change_amount' not in columns:
            return True

        # Verificação 3: Novas colunas de sessão e cliente
        if 'session_sale_id' not in columns or 'customer_name' not in columns:
            return True

        # Verificação 4: Coluna peso_kg para açaí
        cursor.execute("PRAGMA table_info(sale_items)")
        sale_items_columns = [col['name'] for col in cursor.fetchall()]
        if 'peso_kg' not in sale_items_columns:
            return True

        # Verificação 5: Coluna 'price' inesperada na tabela de estoque
        try:
            cursor.execute("PRAGMA table_info(estoque_itens)")
            estoque_columns = [col['name'] for col in cursor.fetchall()]
            if 'price' in estoque_columns:
                return True
        except sqlite3.OperationalError:
            # A tabela pode não existir ainda, o que é normal.
            pass

        # Verificação para credit_sales_old: Se credit_sales_old existe, migração é necessária.
        try:
            cursor.execute("PRAGMA table_info(credit_sales_old)")
            logging.warning("Detectada tabela 'credit_sales_old'. Migração de fiados será executada.")
            logging.debug("DEBUG: is_any_migration_needed - Returning True due to credit_sales_old.") # NEW LOG
            return True
        except sqlite3.OperationalError:
            # Tabela credit_sales_old não existe.
            pass

        # Verificação 6: Coluna customer_id em credit_sales
        credit_sales_exists = False
        try:
            cursor.execute("PRAGMA table_info(credit_sales)")
            credit_sales_columns = [col['name'] for col in cursor.fetchall()]
            credit_sales_exists = True
            if 'customer_id' not in credit_sales_columns:
                return True
        except sqlite3.OperationalError:
            # Tabela credit_sales não existe.
            pass

        # Verificação 7: Constraint de status em credit_sales (só se a tabela credit_sales existir)
        if credit_sales_exists and is_credit_sales_constraint_broken():
            return True

        # Verificação 8: Coluna cash_session_id em credit_payments
        try:
            cursor.execute("PRAGMA table_info(credit_payments)")
            credit_payments_columns = [col['name'] for col in cursor.fetchall()]
            if 'cash_session_id' not in credit_payments_columns:
                return True
        except sqlite3.OperationalError:
            # Tabela pode não existir, o que é ok, será criada depois.
            pass

        return False
    finally:
        conn.close()

def check_migration_needed():
    """Verifica se a migração é necessária."""
    conn = get_db_connection()

    try:
        # Verifica se a tabela sales tem a coluna payment_method
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(sales)")
        columns = cursor.fetchall()
        has_payment_method_column = any(col['name'] == 'payment_method' for col in columns)

        # Verifica se a tabela sale_payments existe
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='sale_payments'")
        has_sale_payments_table = cursor.fetchone() is not None

        return has_payment_method_column and not has_sale_payments_table

    finally:
        conn.close()

def add_change_amount_column():
    """MIGRATION 2: Adiciona a coluna 'change_amount' à tabela 'sales'."""
    logging.info("Executando migração: Adicionar coluna 'change_amount'...")
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("PRAGMA table_info(sales)")
        columns = [column['name'] for column in cursor.fetchall()]
        if 'change_amount' not in columns:
            cursor.execute("ALTER TABLE sales ADD COLUMN change_amount INTEGER NOT NULL DEFAULT 0")
            logging.info("   ✅ Coluna 'change_amount' adicionada à tabela 'sales'.")
        else:
            logging.info("   ✅ Coluna 'change_amount' já existe. Nenhuma ação necessária.")
    except sqlite3.Error as e:
        logging.error(f"   ❌ Erro ao adicionar coluna 'change_amount': {e}")
    finally:
        conn.commit()
        conn.close()

def add_session_and_customer_columns():
    """MIGRATION 3: Adiciona as colunas 'session_sale_id' e 'customer_name' à tabela 'sales'."""
    logging.info("Executando migração: Adicionar colunas de sessão e cliente...")
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("PRAGMA table_info(sales)")
        columns = [column['name'] for column in cursor.fetchall()]
        
        if 'session_sale_id' not in columns:
            cursor.execute("ALTER TABLE sales ADD COLUMN session_sale_id INTEGER")
            logging.info("   ✅ Coluna 'session_sale_id' adicionada à tabela 'sales'.")
        else:
            logging.info("   ✅ Coluna 'session_sale_id' já existe.")

        if 'customer_name' not in columns:
            cursor.execute("ALTER TABLE sales ADD COLUMN customer_name TEXT")
            logging.info("   ✅ Coluna 'customer_name' adicionada à tabela 'sales'.")
        else:
            logging.info("   ✅ Coluna 'customer_name' já existe.")
    except sqlite3.Error as e:
        logging.error(f"   ❌ Erro ao adicionar colunas de sessão/cliente: {e}")
    finally:
        conn.commit()
        conn.close()

def add_customer_id_to_credit_sales():
    """MIGRATION 6: Adiciona a coluna 'customer_id' à tabela 'credit_sales' se não existir."""
    logging.info("Executando migração: Adicionar coluna 'customer_id' a 'credit_sales'...")
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("PRAGMA table_info(credit_sales)")
        columns = [column['name'] for column in cursor.fetchall()]
        if 'customer_id' not in columns:
            # Adiciona a coluna como NULLABLE para evitar erros em tabelas com dados existentes.
            cursor.execute("ALTER TABLE credit_sales ADD COLUMN customer_id INTEGER")
            logging.info("   ✅ Coluna 'customer_id' adicionada à tabela 'credit_sales'.")
        else:
            logging.info("   ✅ Coluna 'customer_id' já existe em 'credit_sales'. Nenhuma ação necessária.")
    except sqlite3.OperationalError as e:
        if "no such table: credit_sales" in str(e):
            logging.info("   ✅ Tabela 'credit_sales' não existe, será criada corretamente. Nenhuma migração necessária.")
        else:
            logging.error(f"   ❌ Erro ao adicionar coluna 'customer_id' a 'credit_sales': {e}")
    except sqlite3.Error as e:
        logging.error(f"   ❌ Erro ao adicionar coluna 'customer_id' a 'credit_sales': {e}")
    finally:
        conn.commit()
        conn.close()

def fix_credit_sales_status_constraint():
    """MIGRATION 7: Popula customer_id em credit_sales com base em customer_name e, em seguida, reconstrói a tabela para remover a coluna customer_name e corrigir as constraints."""
    logging.info("Executando migração: Corrigir e popular a tabela 'credit_sales'...")
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Verifica se a tabela existe
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='credit_sales'")
        credit_sales_exists_in_db = cursor.fetchone()

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='credit_sales_old'")
        credit_sales_old_exists_in_db = cursor.fetchone()

        logging.debug(f"DEBUG: fix_credit_sales_status_constraint - Initial state:")
        logging.debug(f"DEBUG:   credit_sales_exists_in_db: {credit_sales_exists_in_db}")
        logging.debug(f"DEBUG:   credit_sales_old_exists_in_db: {credit_sales_old_exists_in_db}")

        source_table_name = None
        if credit_sales_old_exists_in_db:
            source_table_name = "credit_sales_old"
            logging.info("   ⚠️ Tabela 'credit_sales_old' encontrada. Priorizando migração a partir dela.")
            # Se credit_sales também existe (criada vazia por create_tables), precisamos removê-la
            if credit_sales_exists_in_db:
                logging.warning("   ⚠️ Tabela 'credit_sales' vazia detectada. Removendo para migrar de 'credit_sales_old'.")
                cursor.execute("DROP TABLE credit_sales")
                credit_sales_exists_in_db = None # Marca como não existente após remoção
        elif credit_sales_exists_in_db:
            source_table_name = "credit_sales"
        
        if not source_table_name:
            logging.info("   ✅ Nenhuma tabela de fiado existente para migrar. Será criada do zero. Nenhuma migração necessária.")
            return

        # Verifica se a migração é necessária (ou seja, se a coluna customer_name existe na tabela fonte)
        cursor.execute(f"PRAGMA table_info({source_table_name})")
        columns = [col['name'] for col in cursor.fetchall()]
        
        # Se a fonte é credit_sales_old, sempre migrar, pois sua existência já indica um estado incompleto.
        # Se a fonte é credit_sales, verificar se ela já está no formato correto.
        if source_table_name == "credit_sales" and 'customer_name' not in columns and 'customer_id' in columns:
            logging.info(f"   ✅ Tabela '{source_table_name}' já está no formato correto. Nenhuma migração necessária.")
            return

        logging.info(f"   ⚠️ Tabela '{source_table_name}' está em formato antigo. Iniciando processo de migração de dados...")

        # Passo 1: Adicionar a coluna customer_id se ela não existir na tabela fonte.
        if 'customer_id' not in columns:
            logging.info("      Adicionando a coluna 'customer_id'...")
            cursor.execute(f"ALTER TABLE {source_table_name} ADD COLUMN customer_id INTEGER")
        
        # Passo 2: Popular customer_id a partir de customer_name.
        logging.info("      Populando 'customer_id' a partir de 'customer_name'...")
        cursor.execute(f"SELECT id, customer_name FROM {source_table_name} WHERE customer_id IS NULL")
        sales_to_update = cursor.fetchall()
        updated_count = 0
        not_found_customers = set()

        for sale in sales_to_update:
            customer_name = sale['customer_name']
            if not customer_name:
                continue
            
            # Encontrar cliente por nome (ignorando maiúsculas/minúsculas e espaços)
            cursor.execute("SELECT id FROM customers WHERE trim(lower(name)) = trim(lower(?))", (customer_name,))
            customer = cursor.fetchone()

            if customer:
                cursor.execute(f"UPDATE {source_table_name} SET customer_id = ? WHERE id = ?", (customer['id'], sale['id']))
                updated_count += 1
            else:
                not_found_customers.add(customer_name)
        
        conn.commit()
        logging.info(f"      {updated_count} registros de fiado foram associados a um cliente.")
        if not_found_customers:
            logging.warning(f"      ⚠️ Não foi possível encontrar clientes para os seguintes nomes: {list(not_found_customers)}. Esses fiados não serão migrados.")

        # Passo 3: Reconstruir a tabela para impor NOT NULL e remover customer_name.
        logging.info("      Reconstruindo a tabela 'credit_sales' com o esquema final...")

        cursor.execute(f'ALTER TABLE {source_table_name} RENAME TO credit_sales_temp_migration')

        # Criar a nova tabela com o esquema correto
        cursor.execute('''
            CREATE TABLE credit_sales (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id INTEGER NOT NULL,
                sale_id INTEGER, 
                amount INTEGER NOT NULL, 
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

        # Copiar dados da tabela antiga para a nova, mas apenas para linhas onde encontramos um customer_id
        cursor.execute('''
            INSERT INTO credit_sales (id, customer_id, sale_id, amount, status, observations, created_date, due_date, user_id)
            SELECT id, customer_id, sale_id, amount, status, observations, created_date, due_date, user_id
            FROM credit_sales_temp_migration
            WHERE customer_id IS NOT NULL
        ''')
        
        migrated_rows = cursor.rowcount
        logging.info(f"      {migrated_rows} registros de fiado foram migrados para a nova estrutura.")

        cursor.execute('DROP TABLE credit_sales_temp_migration')

        # Marcar a migração como concluída para evitar que seja executada novamente
        cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", ('credit_sales_migration_v2_done', 'true'))
        
        conn.commit()
        logging.info("   ✅ Migração da tabela 'credit_sales' concluída com sucesso!")

    except sqlite3.Error as e:
        logging.error(f"   ❌ Ocorreu um erro durante a migração de 'credit_sales': {e}", exc_info=True)
        conn.rollback()
    finally:
        conn.close()

def add_cash_session_id_to_credit_payments():
    """MIGRATION 8: Adiciona a coluna 'cash_session_id' à tabela 'credit_payments'."""
    logging.info("Executando migração: Adicionar coluna 'cash_session_id' a 'credit_payments'...")
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("PRAGMA table_info(credit_payments)")
        columns = [column['name'] for column in cursor.fetchall()]
        if 'cash_session_id' not in columns:
            cursor.execute("ALTER TABLE credit_payments ADD COLUMN cash_session_id INTEGER REFERENCES cash_sessions(id) ON DELETE SET NULL")
            logging.info("   ✅ Coluna 'cash_session_id' adicionada à tabela 'credit_payments'.")
        else:
            logging.info("   ✅ Coluna 'cash_session_id' já existe em 'credit_payments'. Nenhuma ação necessária.")
    except sqlite3.Error as e:
        logging.error(f"   ❌ Erro ao adicionar coluna 'cash_session_id' a 'credit_payments': {e}")
    finally:
        conn.commit()
        conn.close()

def add_quantity_and_stock_columns():
    """MIGRATION 9: Adiciona as colunas 'quantity' e 'stock' à tabela 'products' se não existirem."""
    logging.info("Executando migração: Adicionar colunas 'quantity' e 'stock' a 'products'...")
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("PRAGMA table_info(products)")
        columns = [column['name'] for column in cursor.fetchall()]
        
        if 'stock' not in columns:
            cursor.execute("ALTER TABLE products ADD COLUMN stock INTEGER NOT NULL DEFAULT 0")
            logging.info("   ✅ Coluna 'stock' adicionada à tabela 'products'.")
        else:
            logging.info("   ✅ Coluna 'stock' já existe em 'products'.")

        if 'quantity' not in columns:
            cursor.execute("ALTER TABLE products ADD COLUMN quantity INTEGER NOT NULL DEFAULT 0")
            logging.info("   ✅ Coluna 'quantity' adicionada à tabela 'products'.")
            # Copia os valores de 'stock' para 'quantity' para manter a consistência
            cursor.execute("UPDATE products SET quantity = stock")
            logging.info("   ✅ Valores da coluna 'stock' copiados para 'quantity'.")
        else:
            logging.info("   ✅ Coluna 'quantity' já existe em 'products'.")
            
    except sqlite3.Error as e:
        logging.error(f"   ❌ Erro ao adicionar colunas 'quantity' e 'stock' a 'products': {e}")
    finally:
        conn.commit()
        conn.close()

def run_all_migrations():
    """Executa todas as migrações de banco de dados em sequência."""
    logging.info("🔧 Verificando necessidade de todas as migrações...")
    
    # Migração 1: Múltiplos pagamentos
    if check_migration_needed():
        logging.info("   📋 Migração de múltiplos pagamentos necessária. Executando...")
        success = migrate_database()
        if success:
            logging.info("   ✅ Migração de múltiplos pagamentos executada com sucesso!")
        else:
            logging.error("   ❌ Falha na migração de múltiplos pagamentos.")
    else:
        logging.info("   ✅ Nenhuma migração de múltiplos pagamentos necessária.")

    # Migração 2: Coluna de troco
    add_change_amount_column()

    # Migração 3: Colunas de sessão e cliente
    add_session_and_customer_columns()

    # Migração 4: Coluna de peso para açaí
    add_peso_kg_column()

    # Migração 5: Corrigir schema da tabela de estoque de insumos
    fix_estoque_itens_schema()

    # Migração 6: Adicionar customer_id a credit_sales
    add_customer_id_to_credit_sales()

    # Migração 7: Corrigir a constraint de status em credit_sales
    fix_credit_sales_status_constraint()

    # Migração 8: Adicionar cash_session_id a credit_payments
    add_cash_session_id_to_credit_payments()

    # Migração 9: Adicionar colunas 'quantity' e 'stock' a 'products'
    add_quantity_and_stock_columns()

    # Migração 3: Adicionar colunas de sincronização
    _run_migration_003_add_sync_columns()

    logging.info("🎉 Processo de migração finalizado.")

def fix_estoque_itens_schema():
    """MIGRATION 5: Remove a coluna 'price' da tabela 'estoque_itens' se ela existir."""
    logging.info("Executando migração: Corrigir schema da tabela 'estoque_itens'...")
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("PRAGMA table_info(estoque_itens)")
        columns = [column['name'] for column in cursor.fetchall()]
        
        if 'price' in columns:
            logging.warning("   ⚠️ Coluna 'price' encontrada em 'estoque_itens'. Recriando a tabela com o schema correto...")
            
            # 1. Renomear tabela antiga
            cursor.execute("ALTER TABLE estoque_itens RENAME TO estoque_itens_old")

            # 2. Criar tabela nova com o schema correto (sem a coluna price)
            cursor.execute('''
                CREATE TABLE estoque_itens (
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

            # 3. Copiar dados da tabela antiga para a nova, mapeando a coluna de código
            old_columns = [col['name'] for col in cursor.execute("PRAGMA table_info(estoque_itens_old)").fetchall()]

            # Define as colunas da nova tabela que queremos preencher
            new_table_cols = ["id", "codigo", "nome", "grupo_id", "estoque_atual", "estoque_minimo", "unidade_medida"]
            
            # Mapeia as colunas da nova tabela para as colunas da tabela antiga
            select_exprs = []
            for col in new_table_cols:
                if col == 'codigo':
                    # Mapeia a nova coluna 'codigo' para a antiga 'barcode' ou 'codigo'
                    if 'barcode' in old_columns:
                        select_exprs.append('barcode')
                    elif 'codigo' in old_columns:
                        select_exprs.append('codigo')
                    else:
                        # Se nenhuma coluna de código existir, insere NULL (ou um valor padrão)
                        # mas a coluna é NOT NULL, então isso falharia de qualquer maneira.
                        # O mais seguro é levantar um erro aqui se a coluna de código não for encontrada.
                        raise sqlite3.OperationalError("Não foi possível encontrar a coluna 'codigo' ou 'barcode' na tabela de estoque antiga.")
                elif col in old_columns:
                    select_exprs.append(col)
                else:
                    # Se uma coluna da nova tabela não existia na antiga, usa NULL
                    select_exprs.append('NULL')

            insert_cols_str = ", ".join(new_table_cols)
            select_cols_str = ", ".join(select_exprs)

            cursor.execute(f'INSERT INTO estoque_itens ({insert_cols_str}) SELECT {select_cols_str} FROM estoque_itens_old')

            # 4. Deletar tabela antiga
            cursor.execute("DROP TABLE estoque_itens_old")
            logging.info("   ✅ Tabela 'estoque_itens' recriada com sucesso sem a coluna 'price'.")
        else:
            logging.info("   ✅ Schema da tabela 'estoque_itens' já está correto. Nenhuma ação necessária.")

    except sqlite3.OperationalError as e:
        # Isso pode acontecer se a tabela estoque_itens ainda não existir, o que é seguro ignorar.
        if "no such table" in str(e):
            logging.info("   ✅ Tabela 'estoque_itens' não existe, será criada corretamente. Nenhuma migração necessária.")
        else:
            logging.error(f"   ❌ Erro ao corrigir o schema de 'estoque_itens': {e}")
    except sqlite3.Error as e:
        logging.error(f"   ❌ Erro ao corrigir o schema de 'estoque_itens': {e}")
    finally:
        conn.commit()
        conn.close()


def add_peso_kg_column():
    """MIGRATION 4: Adiciona a coluna 'peso_kg' à tabela 'sale_items'."""
    logging.info("Executando migração: Adicionar coluna 'peso_kg'...")
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("PRAGMA table_info(sale_items)")
        columns = [column['name'] for column in cursor.fetchall()]
        if 'peso_kg' not in columns:
            cursor.execute("ALTER TABLE sale_items ADD COLUMN peso_kg REAL")
            logging.info("   ✅ Coluna 'peso_kg' adicionada à tabela 'sale_items'.")
        else:
            logging.info("   ✅ Coluna 'peso_kg' já existe. Nenhuma ação necessária.")
    except sqlite3.Error as e:
        logging.error(f"   ❌ Erro ao adicionar coluna 'peso_kg': {e}")
    finally:
        conn.commit()
        conn.close()


def add_peso_kg_column():
    """MIGRATION 4: Adiciona a coluna 'peso_kg' à tabela 'sale_items'."""
    logging.info("Executando migração: Adicionar coluna 'peso_kg'...")
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("PRAGMA table_info(sale_items)")
        columns = [column['name'] for column in cursor.fetchall()]
        if 'peso_kg' not in columns:
            cursor.execute("ALTER TABLE sale_items ADD COLUMN peso_kg REAL")
            logging.info("   ✅ Coluna 'peso_kg' adicionada à tabela 'sale_items'.")
        else:
            logging.info("   ✅ Coluna 'peso_kg' já existe. Nenhuma ação necessária.")
    except sqlite3.Error as e:
        logging.error(f"   ❌ Erro ao adicionar coluna 'peso_kg': {e}")
    finally:
        conn.commit()
        conn.close()


def _run_migration_001_add_credit_sale_due_date(cursor):
    logging.warning("Função de migração _run_migration_001_add_credit_sale_due_date não implementada.")
    pass

def _run_migration_002_add_stock_tables(cursor):
    logging.warning("Função de migração _run_migration_002_add_stock_tables não implementada.")
    pass

def _run_migration_004_fix_missing_sync_columns(cursor):
    """
    Migração 004: Adiciona colunas de sincronização a tabelas
    que foram esquecidas na migração 003.
    """
    logging.info("Executando migração 004: Adicionando colunas de sincronização faltantes...")

    # Tabelas transacionais que faltaram
    tables_to_fix = [
        'cash_sessions',
        'cash_movements',
        'cash_counts',
        'sale_payments',
        'audit_log'
        # 'pedidos_externos_pendentes' pode ser adicionada se necessário
    ]

    for table in tables_to_fix:
        logging.info(f"Processando tabela: {table}")

        _add_column_if_not_exists(cursor, table, 'id_web', 'TEXT UNIQUE')
        _add_column_if_not_exists(cursor, table, 'sync_status', "TEXT NOT NULL DEFAULT 'pending_create'")
        _add_column_if_not_exists(cursor, table, 'last_modified_at', "TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP")

        # Recriar Trigger para atualizar 'last_modified_at'
        trigger_name = f"trg_{table}_update_last_modified"
        cursor.execute(f"DROP TRIGGER IF EXISTS {trigger_name}")
        cursor.execute(f"""
            CREATE TRIGGER {trigger_name}
            AFTER UPDATE ON {table}
            FOR EACH ROW
            BEGIN
                UPDATE {table}
                SET last_modified_at = CURRENT_TIMESTAMP
                WHERE id = OLD.id;
            END;
        """)

        logging.info(f"Tabela '{table}' atualizada para sincronização.")

    logging.info("Migração 004 concluída com sucesso.")

MIGRATIONS = [
    ('001_add_credit_sale_due_date', _run_migration_001_add_credit_sale_due_date),
    ('002_add_stock_tables', _run_migration_002_add_stock_tables),
    ('003_add_sync_columns', _run_migration_003_add_sync_columns),
    ('004_fix_missing_sync_columns', _run_migration_004_fix_missing_sync_columns),
]

if __name__ == '__main__':
    run_all_migrations()
