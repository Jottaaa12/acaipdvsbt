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

DB_FILE = get_data_path('pdv.db')

def get_db_connection():
    """Cria e retorna uma conexão com o banco de dados."""
    conn = sqlite3.connect(DB_FILE)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn

def migrate_database():
    """Executa a migração do banco de dados."""
    print("Iniciando migração do banco de dados...")

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Verifica se a tabela sales ainda tem a coluna payment_method
        cursor.execute("PRAGMA table_info(sales)")
        columns = cursor.fetchall()
        has_payment_method_column = any(col['name'] == 'payment_method' for col in columns)

        if not has_payment_method_column:
            print("✅ Migração já foi executada anteriormente. Nenhuma ação necessária.")
            return True

        print("📋 Iniciando processo de migração...")

        # 1. Criar nova tabela sale_payments
        print("   Criando tabela sale_payments...")
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
        print("   Migrando dados existentes...")

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

        # 3. Remover coluna payment_method da tabela sales
        print("   Removendo coluna payment_method da tabela sales...")
        cursor.execute('ALTER TABLE sales DROP COLUMN payment_method')

        # 4. Criar índice para a nova tabela
        print("   Criando índices...")
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_sale_payments_sale_id ON sale_payments (sale_id)')

        conn.commit()
        print("✅ Migração concluída com sucesso!")

        # Verificar se há dados migrados
        cursor.execute('SELECT COUNT(*) FROM sale_payments')
        migrated_count = cursor.fetchone()[0]

        print(f"📊 {migrated_count} registros de pagamento migrados.")

        return True

    except sqlite3.Error as e:
        print(f"❌ Erro durante a migração: {e}")
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
                print(f"   ⚠️  Erro ao fazer parsing do pagamento: {method}: R$ {amount_str}")
                continue

        # Verificar se a soma dos pagamentos é igual ao total
        total_payments = sum(p['amount'] for p in payments_list)
        if abs(total_payments - Decimal(str(total_amount)) / 100) > Decimal('0.01'):
            print(f"   ⚠️  Diferença de valor detectada na venda. Total: {total_amount/100}, Pagamentos: {total_payments}")
    else:
        # Se não conseguiu extrair, assume que é um único método de pagamento
        payments_list = [{'method': payment_string, 'amount': Decimal(str(total_amount)) / 100}]

    return payments_list

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

if __name__ == '__main__':
    print("🔧 Verificando necessidade de migração...")

    if check_migration_needed():
        print("📋 Migração necessária. Executando...")
        success = migrate_database()

        if success:
            print("✅ Migração executada com sucesso!")
            print("🎉 O sistema agora suporta múltiplos pagamentos por venda!")
        else:
            print("❌ Falha na migração. Verifique os logs de erro acima.")
    else:
        print("✅ Nenhuma migração necessária. O banco já está atualizado.")
