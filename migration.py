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

    logging.info("🎉 Processo de migração finalizado.")


if __name__ == '__main__':
    run_all_migrations()
