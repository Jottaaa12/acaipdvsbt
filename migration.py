'''
Script de migração para atualizar o esquema do banco de dados.
'''
import sqlite3

DB_FILE = 'pdv.db'

def run_migration():
    '''Executa as alterações necessárias no banco de dados.'''
    conn = None
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        print("Conectado ao banco de dados para migração.")

        # Verificar se a coluna 'quantity' já existe na tabela products
        cursor.execute("PRAGMA table_info(products)")
        columns = cursor.fetchall()
        column_names = [column[1] for column in columns]

        if 'quantity' not in column_names:
            print("Iniciando migração para adicionar coluna 'quantity' e converter 'stock' para INTEGER...")

            # 1. Renomear tabela atual
            cursor.execute('ALTER TABLE products RENAME TO products_old')
            print("Tabela 'products' renomeada para 'products_old'.")

            # 2. Criar nova tabela com estrutura atualizada
            cursor.execute('''
                CREATE TABLE products (
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
            print("Nova tabela 'products' criada com colunas 'stock' e 'quantity' como INTEGER.")

            # 3. Migrar dados convertendo valores para INTEGER (multiplicando por 1000)
            cursor.execute('''
                INSERT INTO products (id, description, barcode, price, stock, quantity, sale_type, group_id)
                SELECT
                    id,
                    description,
                    barcode,
                    price,
                    CAST(stock * 1000 AS INTEGER),
                    CAST(stock * 1000 AS INTEGER),
                    sale_type,
                    group_id
                FROM products_old
            ''')
            print("Dados migrados com valores multiplicados por 1000 para maior precisão.")

            # 4. Remover tabela antiga
            cursor.execute('DROP TABLE products_old')
            print("Tabela 'products_old' removida.")
        else:
            print("Coluna 'quantity' já existe. Verificando se há outras migrações necessárias...")

        # Adicionar a coluna authorized_by_id à tabela cash_movements
        try:
            cursor.execute('ALTER TABLE cash_movements ADD COLUMN authorized_by_id INTEGER REFERENCES users(id)')
            print("Coluna 'authorized_by_id' adicionada com sucesso à tabela 'cash_movements'.")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e):
                print("A coluna 'authorized_by_id' já existe em 'cash_movements'.")
            else:
                raise

        # Adicionar a coluna observations à tabela cash_sessions
        try:
            cursor.execute('ALTER TABLE cash_sessions ADD COLUMN observations TEXT')
            print("Coluna 'observations' adicionada com sucesso à tabela 'cash_sessions'.")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e):
                print("A coluna 'observations' já existe em 'cash_sessions'.")
            else:
                raise

        # --- Nova Tabela: sale_payments ---
        try:
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS sale_payments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sale_id INTEGER NOT NULL,
                    method TEXT NOT NULL,
                    amount INTEGER NOT NULL,
                    FOREIGN KEY (sale_id) REFERENCES sales (id) ON DELETE CASCADE
                )
            ''')
            print("Tabela 'sale_payments' criada ou já existente.")
            # Adicionar índice para melhorar a performance de buscas por sale_id
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_sale_payments_sale_id ON sale_payments (sale_id);')
            print("Índice para 'sale_payments.sale_id' criado ou já existente.")
        except sqlite3.Error as e:
            print(f"Erro ao criar a tabela 'sale_payments': {e}")
            raise # Levanta o erro para abortar a transação

        conn.commit()
        print("Migração do banco de dados concluída com sucesso.")

    except sqlite3.Error as e:
        print(f"Ocorreu um erro durante a migração do banco de dados: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()
            print("Conexão com o banco de dados fechada.")

if __name__ == '__main__':
    run_migration()
